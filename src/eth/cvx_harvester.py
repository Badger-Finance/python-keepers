"""
Why not use brownie?
"""

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
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from flashbots import flashbot

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from harvester import IHarvester
from utils import (
    confirm_transaction,
    get_coingecko_price,
    send_error_to_discord,
    send_success_to_discord,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
CVX_ADDRESS = "0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B"

FEE_THRESHOLD = 1  # ratio of gas cost to harvest amount we're ok with


class CvxHarvester(IHarvester):
    def __init__(
        self,
        keeper_address,
        keeper_key,
        node_url,
    ):
        self.logger = logging.getLogger()
        self.web3 = Web3(Web3.HTTPProvider(node_url))
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_USD_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.cvx = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(CVX_ADDRESS),
            abi=self.__get_abi("cvx"),
        )
        self.cvx_decimals = self.cvx.functions.decimals().call()

        # TODO: Maybe move outside class
        # Account which signifies your identify to flashbots network
        FLASHBOTS_SIGNER: LocalAccount = Account.from_key(
            os.getenv("FLASHBOTS_SIGNER_KEY")
        )
        flashbot(self.web3, FLASHBOTS_SIGNER)

    def __get_abi(self, contract_id: str):
        with open(f"./abi/eth/{contract_id}.json") as f:
            return json.load(f)

    def harvest(
        self,
        sett_name: str,
        strategy_address: str,
    ):
        """Orchestration function that harvests outstanding CVX awards.

        Args:
            sett_name (str)
            strategy_address (str)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        strategy = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(strategy_address),
            abi=self.__get_abi("cvx_helper_strategy"),
        )

        if not self.__is_keeper_whitelisted(strategy):
            raise ValueError(f"Keeper is not whitelisted for {sett_name}")

        # TODO: Harvest call might require some ERC20 token approvals to prevent reverts
        #       Maybe use mainnet fork and add those call()s to get_harvestable_rewards_amount
        harvestable_amount = self.get_harvestable_rewards_amount(
            strategy_address=strategy_address
        )
        self.logger.info(f"harvestable amount: {harvestable_amount}")

        current_price_eth = self.get_current_rewards_price()
        self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy)

        should_harvest = self.is_profitable(
            harvestable_amount, current_price_eth, gas_fee
        )
        should_harvest = True
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
                harvested=harvestable_amount * current_price_eth * eth_usd_price,
            )

    def get_harvestable_rewards_amount(
        self,
        strategy_address: str = None,
    ) -> Decimal:
        """Get integer amount of outstanding awards waiting to be harvested.

        Args:
            strategy_address (str, optional): Defaults to None.

        Returns:
            Decimal: Integer amount of outstanding awards available for harvest.
        """
        strategy = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(strategy_address),
            abi=self.__get_abi("cvx_helper_strategy"),
        )

        harvestable_amt = (
            strategy.functions.harvest().call({"from": self.keeper_address})
            / 10 ** self.cvx_decimals
        )
        return Decimal(harvestable_amt)

    def get_current_rewards_price(self) -> Decimal:
        """Get price of CVX in ETH.

        Returns:
            Decimal: Price per CVX denominated in ETH
        """
        # TODO: Find a reliable oracle or off-chain API to get current price
        return Decimal(get_coingecko_price(CVX_ADDRESS, base="eth"))

    def is_profitable(
        self, amount: Decimal, price_per: Decimal, gas_fee: Decimal
    ) -> bool:
        """Checks if harvesting is profitable based on amount of awards and cost to harvest.

        Args:
            amount (Decimal): Integer amount of CVX available for harvest
            price_per (Decimal): Price per CVX in ETH
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
            harvested (Decimal, optional): Amount of CVX harvested. Defaults to None.
        """
        tx_hash = HexBytes(0)
        try:
            tx_hash, target_block = self.__send_harvest_tx(strategy, overrides)
            succeeded = confirm_transaction(self.web3, tx_hash, target_block)
            if succeeded:
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                send_success_to_discord(
                    tx_hash, sett_name, gas_price_of_tx, harvested, "Harvest"
                )
            elif tx_hash:
                send_error_to_discord(sett_name, "Harvest", tx_hash=tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            tx_hash = "invalid" if tx_hash == HexBytes(0) else tx_hash
            error = e
            send_error_to_discord(sett_name, "Harvest", tx_hash=tx_hash, error=error)

    def __send_harvest_tx(
        self, contract: contract, overrides: dict, use_flashbots=False
    ) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            contract (contract)
            overrides (dict)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
            int: Target block for transaction that was sent.
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
            tx_hash = signed_tx.hash
            target_block = None

            if not use_flashbots:
                self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            else:
                bundle = [
                    {"signed_transaction": signed_tx.rawTransaction},
                ]

                block_number = self.web3.eth.block_number
                block_offset = 1
                target_block = block_number + block_offset

                self.web3.flashbots.send_bundle(
                    bundle, target_block_number=target_block
                )
                self.logger(f"Bundle broadcasted at {target_block}")

                # num_bundles = 1
                # for i in range(1, num_bundles + 1):
                #     self.web3.flashbots.send_bundle(bundle, target_block_number=block_number + i)

        except Exception as e:
            self.logger.error(f"Error in sending harvest tx: {e}")
            tx_hash = HexBytes(0)
            target_block = None
            raise Exception
        finally:
            return tx_hash, target_block

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
