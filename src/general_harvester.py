from decimal import Decimal
from hexbytes import HexBytes
import json
import logging
import os
import requests
import sys
from time import sleep
from web3 import Web3, contract, exceptions

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))

from harvester import IHarvester
from utils import send_error_to_discord, send_success_to_discord, get_abi

logging.basicConfig(level=logging.INFO)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
SUSHI_ETH_CHAINLINK = "0xe572CeF69f43c2E488b33924AF04BDacE19079cf"
WBTC_ETH_STRATEGY = "0x7A56d65254705B4Def63c68488C0182968C452ce"
WBTC_DIGG_STRATEGY = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
WBTC_BADGER_STRATEGY = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
SUSHI_ADDRESS = "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2"
XSUSHI_ADDRESS = "0x8798249c2E607446EfB7Ad49eC89dD1865Ff4272"
HARVEST_THRESHOLD = 0.0005  # min ratio of want to total vault AUM required to harvest


class GeneralHarvester(IHarvester):
    def __init__(
        self,
        chain: str = "eth",
        keeper_address: str = os.getenv("KEEPER_ADDRESS"),
        keeper_key: str = os.getenv("KEEPER_KEY"),
        web3: str = os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger("harvester")
        self.chain = chain
        self.web3 = Web3(Web3.HTTPProvider(web3))
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_USD_CHAINLINK),
            abi=get_abi(self.chain, "oracle"),
        )

    def harvest(
        self,
        sett_name: str,
        strategy: contract,
    ):
        """Orchestration function that harvests outstanding rewards.

        Args:
            sett_name (str)
            strategy_address (str)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        # TODO: update for ACL
        if not self.__is_keeper_whitelisted(strategy):
            raise ValueError(f"Keeper is not whitelisted for {sett_name}")

        want_address = strategy.functions.want().call()
        want = self.web3.eth.contract(
            address=want_address,
            abi=get_abi(self.chain, "erc20"),
        )
        vault_balance = want.functions.balanceOf(strategy.address)
        self.logger.info(f"claimable rewards: {vault_balance}")

        want_to_harvest = strategy.functions.harvest().call()
        self.logger.info(f"claimable rewards: {want_to_harvest}")

        # TODO: figure out how to handle profit estimation
        # current_price_eth = self.get_current_rewards_price()
        # self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        # TODO: estimate gas fee for different chains
        # gas_fee = self.estimate_gas_fee(strategy)

        # TODO: should_harvest check reworked
        # harvest if ideal want change is > 0.05% of total vault assets 
        should_harvest = want_to_harvest / vault_balance >= HARVEST_THRESHOLD
        self.logger.info(f"Should we harvest: {should_harvest}")

        if should_harvest:
            self.__process_harvest(
                strategy=strategy,
                sett_name=sett_name,
                overrides={
                    "from": self.keeper_address,
                    "allow_revert": True,
                },
                harvested=want_to_harvest / want.functions.decimals().call(),
            )

    def __is_keeper_whitelisted(self, strategy: contract) -> bool:
        """Checks if the bot we're using is whitelisted for the strategy.

        Args:
            strategy (contract)

        Returns:
            bool: True if our bot is whitelisted to make function calls to strategy,
            False otherwise.
        """
        return strategy.functions.keeper().call() == self.keeper_address

    def __process_harvest(
        self,
        strategy: contract = None,
        sett_name: str = None,
        overrides: dict = None,
        harvested: Decimal = None,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            strategy (contract, optional): Defaults to None.
            sett_name (str, optional): Defaults to None.
            overrides (dict, optional): Dictionary settings for transaction. Defaults to None.
            harvested (Decimal, optional): Amount of Sushi harvested. Defaults to None.
        """
        error = None
        try:
            tx_hash = self.__send_harvest_tx(strategy, overrides)
            succeeded = self.confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                send_success_to_discord(
                    tx_hash, sett_name, gas_price_of_tx, harvested, "Harvest"
                )
            elif tx_hash:
                send_error_to_discord(sett_name, "Harvest", tx_hash=tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            error = e
            send_error_to_discord(sett_name, "Harvest", error=error)

    def __send_harvest_tx(self, contract: contract, overrides: dict) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            contract (contract)
            overrides (dict)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            tx = contract.functions.harvest().buildTransaction(
                {
                    "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
                    "gasPrice": self.__get_gas_price(),
                    "from": self.keeper_address,
                }
            )
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except Exception as e:
            self.logger.error(f"Error in sending harvest tx: {e}")
            tx_hash = HexBytes(0)
            raise Exception
        finally:
            return tx_hash

    def estimate_gas_fee(self, strategy: contract) -> Decimal:
        current_gas_price = self.__get_gas_price()
        estimated_gas_to_harvest = strategy.functions.harvest().estimateGas(
            {"from": strategy.functions.keeper().call()}
        )
        return Decimal(current_gas_price * estimated_gas_to_harvest)

    def __get_gas_price(self) -> int:
        response = requests.get(
            "https://www.gasnow.org/api/v3/gas/price?utm_source=BadgerKeeper"
        )
        return int(response.json().get("data").get("rapid") * 1.1)

    def __get_gas_price_of_tx(self, tx_hash: HexBytes) -> Decimal:
        tx = self.web3.eth.get_transaction(tx_hash)

        total_gas_used = Decimal(tx.get("gas", 0))
        gas_price_eth = Decimal(tx.get("gasPrice", 0) / 10 ** 18)
        eth_usd = Decimal(
            self.eth_usd_oracle.functions.latestRoundData().call()[1] / 10 ** 8
        )

        return total_gas_used * gas_price_eth * eth_usd
