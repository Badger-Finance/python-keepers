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
from utils import (
    confirm_transaction,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
    get_hash_from_failed_tx_error,
)

logging.basicConfig(level=logging.INFO)

HARVEST_THRESHOLD = 0.0005  # min ratio of want to total vault AUM required to harvest


class GeneralHarvester(IHarvester):
    def __init__(
        self,
        chain: str = "eth",
        keeper_acl: str = os.getenv("KEEPER_ACL"),
        keeper_address: str = os.getenv("KEEPER_ADDRESS"),
        keeper_key: str = os.getenv("KEEPER_KEY"),
        base_oracle_address: str = os.getenv("ETH_USD_CHAINLINK"),
        web3: str = os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger("harvester")
        self.chain = chain
        self.web3 = Web3(Web3.HTTPProvider(web3))
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.keeper_acl = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(keeper_acl),
            abi=get_abi(self.chain, "keeper_acl"),
        )
        self.base_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(base_oracle_address),
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
        vault_balance = want.functions.balanceOf(strategy.address).call()
        self.logger.info(f"vault balance: {vault_balance}")

        want_to_harvest = self.keeper_acl.functions.harvest(strategy.address).call(
            {"from": self.keeper_address}
        )
        self.logger.info(f"estimated want change: {want_to_harvest}")

        # TODO: figure out how to handle profit estimation
        # current_price_eth = self.get_current_rewards_price()
        # self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy.address)
        self.logger.info(f"estimated gas cost: {gas_fee}")

        # harvest if ideal want change is > 0.05% of total vault assets
        # should_harvest = want_to_harvest / vault_balance >= HARVEST_THRESHOLD

        # for now we'll just harvest every hour
        should_harvest = True
        self.logger.info(f"Should we harvest: {should_harvest}")

        if should_harvest:
            self.__process_harvest(
                strategy=strategy,
                sett_name=sett_name,
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
        harvester_key = self.keeper_acl.functions.HARVESTER_ROLE().call()
        return self.keeper_acl.functions.hasRole(
            harvester_key, self.keeper_address
        ).call()

    def __process_harvest(
        self,
        strategy: contract = None,
        sett_name: str = None,
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
        try:
            tx_hash = self.__send_harvest_tx(strategy)
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                self.logger.info(f"got gas price of tx: ${gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Harvest {sett_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(tx_type=f"Harvest {sett_name}", tx_hash=tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            send_error_to_discord(sett_name, "Harvest", error=e)

    def __send_harvest_tx(self, strategy: contract) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            strategy (contract)
            overrides (dict)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            tx = self.__build_transaction(strategy.address)
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending harvest tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(e, "Harvest")
        finally:
            return tx_hash

    def estimate_gas_fee(self, strategy_address: str) -> Decimal:
        current_gas_price = self.__get_gas_price()
        estimated_gas_to_harvest = self.keeper_acl.functions.harvest(
            strategy_address
        ).estimateGas({"from": self.keeper_address})
        return Decimal(current_gas_price * estimated_gas_to_harvest)

    def __get_gas_price(self) -> int:
        if self.chain == "poly":
            response = requests.get("https://gasstation-mainnet.matic.network").json()
            gas_price = self.web3.toWei(int(response.get("fast") * 1.1), "gwei")
        elif self.chain == "eth":
            response = requests.get(
                "https://www.gasnow.org/api/v3/gas/price?utm_source=BadgerKeeper"
            ).json()
            gas_price = int(response.get("data").get("rapid") * 1.1)

        return gas_price

    def __get_gas_price_of_tx(self, tx_hash: HexBytes) -> Decimal:
        """Gets the actual amount of gas used by the transaction and converts
        it from gwei to USD value for monitoring.

        Args:
            tx_hash (HexBytes): tx id of target transaction

        Returns:
            Decimal: USD value of gas used in tx
        """
        tx = self.web3.eth.get_transaction(tx_hash)

        total_gas_used = Decimal(tx.get("gas", 0))
        gas_price_base = Decimal(tx.get("gasPrice", 0) / 10 ** 18)
        base_usd = Decimal(
            self.base_usd_oracle.functions.latestRoundData().call()[1] / 10 ** 8
        )

        return total_gas_used * gas_price_base * base_usd

    def __build_transaction(self, strategy_address: str) -> dict:
        """Builds transaction depending on which chain we're harvesting. EIP-1559
        requires different handling for ETH txs than the other EVM chains.

        Args:
            contract (contract): contract to use to build harvest tx

        Returns:
            dict: tx dictionary
        """
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
        }
        if self.chain == "eth":
            options["maxPriorityFeePerGas"] = 10
        else:
            options["gasPrice"] = self.__get_gas_price()
        return self.keeper_acl.functions.harvest(strategy_address).buildTransaction(
            options
        )
