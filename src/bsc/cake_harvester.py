from decimal import Decimal
from dotenv import load_dotenv
from hexbytes import HexBytes
import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract, exceptions

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from harvester import IHarvester
from utils import send_error_to_discord, send_success_to_discord, confirm_transaction

load_dotenv()

logging.basicConfig(level=logging.INFO)

GAS_MULTIPLIER = 1.2  # use 20% more gas than node reporting
HARVEST_THRESHOLD = 2  # bnb amount rewards must exceed to claim, reward_amt (BNB) > HARVEST_THRESHOLD (BNB)
CAKE_BNB_CHAINLINK = "0xcB23da9EA243f53194CBc2380A6d4d9bC046161f"
BNB_USD_CHAINLINK = "0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE"
CAKE_ADDRESS = "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"
CAKE_CHEF = "0x73feaa1eE314F8c655E354234017bE2193C9E24E"


class CakeHarvester(IHarvester):
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=Web3(Web3.HTTPProvider(os.getenv("ETH_NODE_URL"))),
    ):
        self.logger = logging.getLogger()
        self.web3 = Web3(Web3.HTTPProvider(web3))
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.bnb_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(BNB_USD_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.cake_bnb_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(CAKE_BNB_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.cake = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(CAKE_ADDRESS),
            abi=self.__get_abi("cake"),
        )
        self.cake_decimals = self.cake.functions.decimals().call()
        self.chef = self.web3.eth.contract(
            address=CAKE_CHEF, abi=self.__get_abi("chef")
        )

    def __get_abi(self, contract_id: str):
        with open(f"./abi/bsc/{contract_id}.json") as f:
            return json.load(f)

    def harvest(
        self,
        sett_name: str,
        strategy_address: str,
    ):
        """Orchestration function that harvests outstanding Cake awards.

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

        pool_id = strategy.functions.wantPid().call()

        claimable_rewards = self.get_harvestable_rewards_amount(
            pool_id=pool_id, strategy_address=strategy_address
        )
        self.logger.info(f"claimable rewards: {claimable_rewards}")

        current_price_bnb = self.get_current_rewards_price()
        self.logger.info(f"current rewards price per token (BNB): {current_price_bnb}")

        should_harvest = self.is_profitable(claimable_rewards, current_price_bnb)
        self.logger.info(f"Should we harvest: {should_harvest}")

        if should_harvest:
            bnb_usd_price = Decimal(
                self.bnb_usd_oracle.functions.latestRoundData().call()[1] / 10 ** 8
            )

            self.__process_harvest(
                strategy=strategy,
                sett_name=sett_name,
                overrides={
                    "from": self.keeper_address,
                    "gas_limit": 12000000,
                    "allow_revert": True,
                },
                harvested=claimable_rewards * current_price_bnb * bnb_usd_price,
            )

    def get_harvestable_rewards_amount(
        self,
        pool_id: int = None,
        strategy_address: str = None,
    ) -> Decimal:
        """Get integer amount of outstanding awards waiting to be harvested.

        Args:
            pool_id (int, optional): Pancake swap liquidity pool id. Defaults to None.
            strategy_address (str, optional): Defaults to None.

        Returns:
            Decimal: Integer amont of outstanding awards available for harvest.
        """
        harvestable_amt = (
            self.chef.functions.pendingCake(pool_id, strategy_address).call()
            / 10 ** self.cake_decimals
        )
        harvestable_amt += (
            self.chef.functions.pendingCake(0, strategy_address).call()
            / 10 ** self.cake_decimals
        )
        return Decimal(harvestable_amt)

    def get_current_rewards_price(self) -> Decimal:
        """Get price of Cake in BNB.

        Returns:
            Decimal: Price per Cake denominated in BNB
        """
        return Decimal(
            self.cake_bnb_oracle.functions.latestRoundData().call()[1]
            / 10 ** self.cake_decimals
        )

    def is_profitable(self, amount: Decimal, price_per: Decimal) -> bool:
        """Checks if harvesting is profitable based on amount of awards and cost to harvest.

        Args:
            amount (Decimal): Integer amount of Cake available for harvest
            price_per (Decimal): Price per Cake in BNB

        Returns:
            bool: True if we should harvest based on amount / cost, False otherwise
        """
        bnb_amount_of_rewards = amount * price_per
        return bnb_amount_of_rewards >= HARVEST_THRESHOLD

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
        """Private function to create, broadcast, confirm tx on bsc and then send
        transaction to Discord for monitoring

        Args:
            strategy (contract, optional): Defaults to None.
            sett_name (str, optional): Defaults to None.
            overrides (dict, optional): Dictionary settings for transaction. Defaults to None.
            harvested (Decimal, optional): Amount of Cake harvested. Defaults to None.
        """
        tx_hash = HexBytes(0)
        try:
            tx_hash = self.__send_harvest_tx(strategy, overrides)
            succeeded, _ = confirm_transaction(tx_hash)
            if succeeded:
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                send_success_to_discord(
                    tx_hash, sett_name, gas_price_of_tx, harvested, "Harvest", "BSC"
                )
            elif tx_hash:
                send_error_to_discord(sett_name, "Harvest", tx_hash=tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            tx_hash = "invalid" if tx_hash == HexBytes(0) else tx_hash
            error = e
            send_error_to_discord(sett_name, "Harvest", tx_hash=tx_hash, error=error)

    def __send_harvest_tx(self, contract: contract, overrides: dict) -> HexBytes:
        """Sends transaction to BSC node for confirmation.

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
                    "gasPrice": self._CakeHarvester__get_gas_price(),
                    "from": self.keeper_address,
                }
            )
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except Exception as e:
            self.logger.error(f"Error sending harvest tx: {e}")
            tx_hash = HexBytes(0)
            raise Exception
        finally:
            return tx_hash

    def __get_gas_price(self):
        return int(self.web3.eth.gas_price * GAS_MULTIPLIER)

    def __get_gas_price_of_tx(self, tx_hash: HexBytes) -> Decimal:
        tx = self.web3.eth.get_transaction(tx_hash)

        total_gas_used = Decimal(tx.get("gas", 0))
        gas_price_bnb = Decimal(tx.get("gasPrice", 0) / 10 ** 18)
        bnb_usd = Decimal(
            self.bnb_usd_oracle.functions.latestRoundData().call()[1] / 10 ** 8
        )

        return total_gas_used * gas_price_bnb * bnb_usd
