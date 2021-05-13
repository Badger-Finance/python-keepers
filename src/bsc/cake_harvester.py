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
from utils import send_transaction_to_discord

load_dotenv()

logging.basicConfig(level=logging.INFO)

GAS_MULTIPLIER = 1.2 # use 20% more gas than node reporting
HARVEST_THRESHOLD = 2  # bnb amount rewards must exceed to claim, reward_amt (BNB) > HARVEST_THRESHOLD (BNB)
CAKE_BNB_CHAINLINK = "0xcB23da9EA243f53194CBc2380A6d4d9bC046161f"
BNB_USD_CHAINLINK = "0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE"
CAKE_ADDRESS = "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"
CAKE_CHEF = "0x73feaa1eE314F8c655E354234017bE2193C9E24E"


class CakeHarvester(IHarvester):
    def __init__(self):
        self.logger = logging.getLogger()
        self.web3 = Web3(Web3.HTTPProvider(os.getenv("BSC_NODE_URL")))
        self.keeper_key = os.getenv("BSC_KEEPER_KEY")
        self.keeper_address = os.getenv("BSC_KEEPER_ADDRESS")
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
                    "gas_limit": 2000000,
                    "allow_revert": True,
                },
                harvested=claimable_rewards * current_price_bnb * bnb_usd_price,
            )

    def get_harvestable_rewards_amount(
        self,
        pool_id: int = None,
        strategy_address: str = None,
    ) -> Decimal:
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
        return Decimal(
            self.cake_bnb_oracle.functions.latestRoundData().call()[1]
            / 10 ** self.cake_decimals
        )

    def is_profitable(self, amount: Decimal, price_per: Decimal) -> bool:
        bnb_amount_of_rewards = amount * price_per
        return bnb_amount_of_rewards >= HARVEST_THRESHOLD

    def __is_keeper_whitelisted(self, strategy: contract) -> bool:
        return True  # strategy.functions.keeper().call() == self.keeper_address

    def __process_harvest(
        self,
        strategy: contract = None,
        sett_name: str = None,
        overrides: dict = None,
        harvested: Decimal = None,
    ):
        error = None
        try:
            tx_hash = self.__send_harvest_tx(strategy, overrides)
            succeeded = self.confirm_transaction(tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            tx_hash = "invalid" if tx_hash == HexBytes(0) else tx_hash
            succeeded = False
            error = e
        finally:
            send_transaction_to_discord(tx_hash, sett_name, harvested, succeeded, error=error)
            

    def __send_harvest_tx(self, contract: contract, overrides: dict) -> HexBytes:
        try:
            tx = contract.functions.harvest().buildTransaction(
                {
                    "nonce": self.web3.eth.getTransactionCount(self.keeper_address),
                    "gasPrice": self.__get_gas_price(),
                    "gasLimit": 12000000
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


        
    
    def confirm_transaction(self, tx_hash: HexBytes):

        try:
            self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        except exceptions.TimeExhausted:
            self.logger.error(f"Transaction timed out, not included in block yet.")
            return False

        self.logger.info(f"Transaction succeeded!")
        return True
        
    def __get_gas_price(self):
        return self.web3.eth.gasPrice * GAS_MULTIPLIER
