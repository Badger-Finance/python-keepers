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
    send_error_to_discord,
    send_rebase_to_discord,
    send_rebase_error_to_discord,
)
from web3 import Web3, contract, exceptions


class Rebaser:
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger()
        self.web3 = Web3(Web3.HTTPProvider(web3))  # get secret here
        self.keeper_key = keeper_key  # get secret here
        self.keeper_address = keeper_address  # get secret here
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("ETH_USD_CHAINLINK")),
            abi=self.__get_abi("oracle"),
        )
        self.digg_token = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("DIGG_TOKEN_ADDRESS")),
            abi=self.__get_abi("digg_token"),
        )
        self.digg_orchestrator = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("DIGG_ORCHESTRATOR_ADDRESS")),
            abi=self.__get_abi("digg_orchestrator"),
        )
        self.digg_policy = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("DIGG_POLICY_ADDRESS")),
            abi=self.__get_abi("digg_policy"),
        )
        self.uni_pair = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("UNIV2_DIGG_WBTC_ADDRESS")),
            abi=self.__get_abi("univ2_pair"),
        )
        self.sushi_pair = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("SUSHI_DIGG_WBTC_ADDRESS")),
            abi=self.__get_abi("sushi_pair"),
        )

    def __get_abi(self, contract_id: str):
        with open(f"./abi/eth/{contract_id}.json") as f:
            return json.load(f)

    def rebase(self):
        # call digg cuntions
        last_rebase_time = self.digg_policy.functions.lastRebaseTimestampSec().call()
        min_rebase_time = self.digg_policy.functions.minRebaseTimeIntervalSec().call()
        in_rebase_window = self.digg_policy.functions.inRebaseWindow().call()
        # can use time.now()
        now = time.time()

        time_since_last_rebase = now - last_rebase_time
        min_time_passed = (last_rebase_time + min_rebase_time) < now

        self.logger.info(
            {
                "last_rebase_time": last_rebase_time,
                "in_rebase_window": in_rebase_window,
                "now": now,
                "time_since_last_rebase": time_since_last_rebase,
                "min_time_passed": min_time_passed,
            }
        )

        # Rebase if sufficient time has passed since last rebase and we are in the window.
        # Give adequate time between TX attempts
        if time_since_last_rebase > hours(2) and in_rebase_window and min_time_passed:
            self.logger.info("📈 Rebase! 📉")

            supply_before = self.digg_token.functions.totalSupply().call()
            spf_before = self.digg_token.functions._sharesPerFragment().call()
            sushi_reserves = self.sushi_pair.functions.getReserves().call()
            uni_reserves = self.uni_pair.functions.getReserves().call()

            self.logger.info(f"spf before: {spf_before}")
            self.logger.info(f"supply before: {supply_before}")
            self.logger.info(f"sushi pair before: {sushi_reserves}")
            self.logger.info(f"uni pair before: {uni_reserves}")

            self.__process_rebase()

            supply_after = self.digg_token.functions.totalSupply().call()
            spf_after = self.digg_token.functions._sharesPerFragment().call()
            sushi_reserves = self.sushi_pair.functions.getReserves().call()
            uni_reserves = self.uni_pair.functions.getReserves().call()

            self.logger.info(f"spfAfter: {spf_after}")
            self.logger.info(f"supply after: {supply_after}")
            self.logger.info(
                f"supply change: %{round((supply_after - supply_before) / supply_before * 100, 2)}"
            )
            self.logger.info(f"sushi reserves after {sushi_reserves}")
            self.logger.info(f"uni reserves after: {uni_reserves}")

            if supply_after > supply_before:
                rebase_type = "positive"
            elif supply_after < supply_before:
                rebase_type = "negative"
            else:
                rebase_type = "neutral"

            return {
                "rebase_type": rebase_type,
                "supply_before": supply_before,
                "supply_after": supply_after,
                "pct_change": f"%{round((supply_after - supply_before) / supply_before * 100, 2)}",
            }
        else:
            self.logger.info("No rebase - conditions not met")
            return "Rebase conditions not met"

    def __process_rebase(self):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring
        """
        try:
            tx_hash = self.__send_rebase_tx()
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                send_rebase_to_discord(tx_hash=tx_hash, gas_cost=gas_price_of_tx)
            elif tx_hash != HexBytes(0):
                send_rebase_to_discord(tx_hash=tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing rebase tx: {e}")
            send_rebase_error_to_discord(error=e)

    def __send_rebase_tx(self) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            tx = self.digg_orchestrator.functions.rebase().buildTransaction(
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
        except ValueError as e:
            self.logger.error(f"Error in sending rebase tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(e, self.logger)
        finally:
            return tx_hash

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
