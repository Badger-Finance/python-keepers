import json
import os
import time

from hexbytes import HexBytes
from web3 import Web3

from config.constants import DIGG
from config.constants import DIGG_ORCHESTRATOR
from config.constants import DIGG_POLICY
from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import SUSHI_DIGG_WBTC
from config.constants import UNIV2_DIGG_WBTC
from config.enums import Network
from src.discord_utils import get_hash_from_failed_tx_error
from src.discord_utils import send_rebase_error_to_discord
from src.discord_utils import send_rebase_to_discord
from src.json_logger import logger
from src.misc_utils import hours
from src.tx_utils import get_effective_gas_price
from src.tx_utils import get_gas_price_of_tx
from src.tx_utils import get_priority_fee
from src.web3_utils import confirm_transaction

MAX_GAS_PRICE = int(1000e9)  # 1000 gwei


class Rebaser:
    def __init__(
        self,
        web3: Web3,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
    ):
        self.web3 = web3
        self.keeper_key = keeper_key  # get secret here
        self.keeper_address = keeper_address  # get secret here
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_ETH_USD_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.digg_token = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(DIGG),
            abi=self.__get_abi("digg_token"),
        )
        self.digg_orchestrator = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(DIGG_ORCHESTRATOR),
            abi=self.__get_abi("digg_orchestrator"),
        )
        self.digg_policy = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(DIGG_POLICY),
            abi=self.__get_abi("digg_policy"),
        )
        self.uni_pair = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(UNIV2_DIGG_WBTC),
            abi=self.__get_abi("univ2_pair"),
        )
        self.sushi_pair = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(SUSHI_DIGG_WBTC),
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

        logger.info(
            "Rebasing",
            extra={
                "last_rebase_time": last_rebase_time,
                "in_rebase_window": in_rebase_window,
                "now": now,
                "time_since_last_rebase": time_since_last_rebase,
                "min_time_passed": min_time_passed,
            },
        )

        # Rebase if sufficient time has passed since last rebase and we are in the window.
        # Give adequate time between TX attempts
        if time_since_last_rebase > hours(2) and in_rebase_window and min_time_passed:
            logger.info("📈 Rebase! 📉")

            supply_before = self.digg_token.functions.totalSupply().call()
            spf_before = self.digg_token.functions._sharesPerFragment().call()
            sushi_reserves = self.sushi_pair.functions.getReserves().call()
            uni_reserves = self.uni_pair.functions.getReserves().call()

            logger.info(f"spf before: {spf_before}")
            logger.info(f"supply before: {supply_before}")
            logger.info(f"sushi pair before: {sushi_reserves}")
            logger.info(f"uni pair before: {uni_reserves}")

            self.__process_rebase()

            supply_after = self.digg_token.functions.totalSupply().call()
            spf_after = self.digg_token.functions._sharesPerFragment().call()
            sushi_reserves = self.sushi_pair.functions.getReserves().call()
            uni_reserves = self.uni_pair.functions.getReserves().call()

            logger.info(f"spfAfter: {spf_after}")
            logger.info(f"supply after: {supply_after}")
            logger.info(
                f"supply change: %{round((supply_after - supply_before) / supply_before * 100, 2)}"
            )
            logger.info(f"sushi reserves after {sushi_reserves}")
            logger.info(f"uni reserves after: {uni_reserves}")

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
            logger.info("No rebase - conditions not met")
            return "Rebase conditions not met"

    def __process_rebase(self):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring
        """
        try:
            tx_hash = self.__send_rebase_tx()
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.eth_usd_oracle, tx_hash, Network.Ethereum
                )
                send_rebase_to_discord(tx_hash=tx_hash, gas_cost=gas_price_of_tx)
            elif tx_hash != HexBytes(0):
                send_rebase_to_discord(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"Error processing rebase tx: {e}")
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
            logger.info(f"max_priority_fee: {self.web3.eth.max_priority_fee}")
            priority_fee = get_priority_fee(self.web3)
            options = {
                "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
                "from": self.keeper_address,
                "maxPriorityFeePerGas": priority_fee,
                "maxFeePerGas": get_effective_gas_price(self.web3),
            }

            tx = self.digg_orchestrator.functions.rebase().buildTransaction(options)
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            logger.error(f"Error in sending rebase tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, logger, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash
