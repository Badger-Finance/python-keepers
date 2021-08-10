from decimal import Decimal
from dotenv import load_dotenv
from hexbytes import HexBytes
import json
import logging
import os
import requests
import sys
from time import sleep
from web3 import Web3, contract, exceptions

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from harvester import IHarvester
from utils import confirm_transaction, send_error_to_discord, send_success_to_discord

load_dotenv()

logging.basicConfig(level=logging.INFO)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
SUSHI_ETH_CHAINLINK = "0xe572CeF69f43c2E488b33924AF04BDacE19079cf"
WBTC_ETH_STRATEGY = "0x7A56d65254705B4Def63c68488C0182968C452ce"
WBTC_DIGG_STRATEGY = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
WBTC_BADGER_STRATEGY = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
SUSHI_ADDRESS = "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2"
XSUSHI_ADDRESS = "0x8798249c2E607446EfB7Ad49eC89dD1865Ff4272"
FEE_THRESHOLD = 0.01  # ratio of gas cost to harvest amount we're ok with


class SushiHarvester(IHarvester):
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=Web3(Web3.HTTPProvider(os.getenv("ETH_NODE_URL"))),
    ):
        self.logger = logging.getLogger()
        self.web3 = web3
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_USD_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.sushi_eth_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(SUSHI_ETH_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.sushi = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(SUSHI_ADDRESS),
            abi=self.__get_abi("sushi"),
        )
        self.xsushi = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(XSUSHI_ADDRESS),
            abi=self.__get_abi("xsushi"),
        )
        self.sushi_decimals = self.sushi.functions.decimals().call()

    def __get_abi(self, contract_id: str):
        with open(f"./abi/eth/{contract_id}.json") as f:
            return json.load(f)

    def harvest(
        self,
        sett_name: str,
        strategy_address: str,
    ):
        """Orchestration function that harvests outstanding Sushi awards.

        Args:
            sett_name (str)
            strategy_address (str)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        strategy = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(strategy_address),
            abi=self.__get_abi("strategy"),
        )

        if not self.__is_keeper_whitelisted(strategy):
            raise ValueError(f"Keeper is not whitelisted for {sett_name}")

        pool_id = strategy.functions.pid().call()

        claimable_rewards = self.get_harvestable_rewards_amount(
            pool_id=pool_id, strategy_address=strategy_address
        )
        self.logger.info(f"claimable rewards: {claimable_rewards}")

        current_price_eth = self.get_current_rewards_price()
        self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy)

        should_harvest = self.is_profitable(
            claimable_rewards, current_price_eth, gas_fee
        )
        self.logger.info(f"Should we harvest: {should_harvest}")

        if should_harvest:
            eth_usd_price = Decimal(
                self.eth_usd_oracle.functions.latestRoundData().call()[1] / 10 ** 8
            )

            self.__process_harvest(
                strategy=strategy,
                sett_name=sett_name,
                overrides={
                    "from": self.keeper_address,
                    "gas_limit": 12000000,
                    "allow_revert": True,
                },
                harvested=claimable_rewards * current_price_eth * eth_usd_price,
            )

    def get_harvestable_rewards_amount(
        self,
        pool_id: int = None,
        strategy_address: str = None,
    ) -> Decimal:
        """Get integer amount of outstanding awards waiting to be harvested.

        Args:
            pool_id (int, optional): Sushi swap liquidity pool id. Defaults to None.
            strategy_address (str, optional): Defaults to None.

        Returns:
            Decimal: Integer amont of outstanding awards available for harvest.
        """
        harvestable_amt = (
            self.xsushi.functions.balanceOf(strategy_address).call()
            / 10 ** self.sushi_decimals
        )
        return Decimal(harvestable_amt)

    def get_current_rewards_price(self) -> Decimal:
        """Get price of Sushi in ETH.

        Returns:
            Decimal: Price per Sushi denominated in ETH
        """
        ratio = (
            self.sushi.functions.balanceOf(self.xsushi.address).call()
            / self.xsushi.functions.totalSupply().call()
        )
        return Decimal(
            (
                self.sushi_eth_oracle.functions.latestRoundData().call()[1]
                / 10 ** self.sushi_decimals
            )
            * ratio
        )

    def is_profitable(
        self, amount: Decimal, price_per: Decimal, gas_fee: Decimal
    ) -> bool:
        """Checks if harvesting is profitable based on amount of awards and cost to harvest.

        Args:
            amount (Decimal): Integer amount of Sushi available for harvest
            price_per (Decimal): Price per Sushi in ETH
            gas_fee (Decimal): gas fee in wei

        Returns:
            bool: True if we should harvest based on amount / cost, False otherwise
        """
        gas_fee_ether = self.web3.fromWei(gas_fee, "ether")
        fee_percent_of_claim = (
            1 if amount * price_per == 0 else gas_fee_ether / (amount * price_per)
        )
        self.logger.info(
            f"Fee as percent of harvest: {round(fee_percent_of_claim * 100, 2)}%"
        )
        return fee_percent_of_claim <= FEE_THRESHOLD

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
            succeeded, _ = confirm_transaction(tx_hash)
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
                    "gas": 12000000,
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
