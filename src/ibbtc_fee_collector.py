from decimal import Decimal
from enum import Enum
from hexbytes import HexBytes
import json
import logging
import os
import requests
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from utils import (
    get_secret,
    hours,
    confirm_transaction,
    get_hash_from_failed_tx_error,
    send_success_to_discord,
    send_oracle_error_to_discord,
)
from tx_utils import get_priority_fee, get_effective_gas_price, get_gas_price_of_tx
from web3 import Web3, contract, exceptions

IBBTC_CORE_ADDRESS = "0x2A8facc9D49fBc3ecFf569847833C380A13418a8"
BTC_ETH_CHAINLINK = "0xdeb288F737066589598e9214E782fa5A8eD689e8"

FEE_THRESHOLD = 0.01  # ratio of gas cost to harvest amount we're ok with
MAX_GAS_PRICE = int(200e9)


class ibBTCFeeCollector:
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger("ibBTC-fee-collector")
        self.web3 = Web3(Web3.HTTPProvider(web3))  # get secret here
        self.keeper_key = keeper_key  # get secret here
        self.keeper_address = keeper_address  # get secret here
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("ETH_USD_CHAINLINK")),
            abi=self.__get_abi("oracle"),
        )
        self.btc_eth_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("BTC_ETH_CHAINLINK")),
            abi=self.__get_abi("oracle"),
        )
        self.ibbtc = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("IBBTC_CORE_ADDRESS")),
            abi=self.__get_abi("ibbtc_core"),
        )

    def __get_abi(self, contract_id: str):
        with open(f"./abi/eth/{contract_id}.json") as f:
            return json.load(f)

    def collect_fees(self):
        # get outstanding fees
        fees = self.get_outstanding_fees()
        self.logger.info(f"Outstanding fees: {fees} BTC")

        # check profitability
        is_profitable = self.__is_profitable(fees)

        # Collect fees if profitable
        if is_profitable:
            self.logger.info(f"Collecting profitable, beginning transaction submission")

            self.__process_collection()
        else:
            self.logger.info("No fee collection - conditions not met")

    def get_outstanding_fees(self) -> Decimal:
        raw_fees = self.ibbtc.functions.accumulatedFee().call()
        return Decimal(raw_fees / 10 ** 18)

    def __is_profitable(self, fees: Decimal) -> bool:
        btc_eth = Decimal(
            self.btc_eth_oracle.functions.latestRoundData().call()[1] / 10 ** 18
        )
        fees_eth = fees * btc_eth
        self.logger.info(f"fees: {fees_eth} ETH")
        gas_fee_wei = self.__estimate_gas_fee()
        gas_fee_eth = self.web3.fromWei(gas_fee_wei, "ether")
        self.logger.info(f"estimated gas fee: {gas_fee_eth} ETH")

        fee_percent_of_claim = 1 if fees_eth == 0 else gas_fee_eth / fees_eth
        return fee_percent_of_claim <= FEE_THRESHOLD

    def __estimate_gas_fee(self) -> Decimal:
        current_gas_price = get_effective_gas_price(self.web3)
        estimated_gas_tx = self.ibbtc.functions.collectFee().estimateGas(
            {"from": self.keeper_address}
        )
        return Decimal(current_gas_price * estimated_gas_tx)

    def __process_collection(self):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring
        """
        try:
            tx_hash = self.__send_collection_tx()
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.eth_usd_oracle, tx_hash, "eth"
                )
                send_success_to_discord(
                    tx_hash=tx_hash,
                    tx_type="ibBTC Fee Collection",
                    gas_cost=gas_price_of_tx,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(tx_hash=tx_hash, tx_type="ibBTC Fee Collection")
        except Exception as e:
            self.logger.error(f"Error processing collection tx: {e}")
            send_oracle_error_to_discord(tx_type="ibBTC Fee Collection", error=e)

    def __send_collection_tx(self) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
            "maxPriorityFeePerGas": get_priority_fee(self.web3),
            "maxFeePerGas": MAX_GAS_PRICE,
        }
        try:
            tx = self.ibbtc.functions.collectFee().buildTransaction(options)
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending collection tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, self.logger, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash
