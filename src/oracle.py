import json
import logging
import os
from datetime import datetime
from datetime import timezone
from traceback import format_exc

import requests
from hexbytes import HexBytes
from web3 import Web3

from config.constants import DIGG_CENTRALIZED_ORACLE
from config.constants import DIGG_CHAINLINK_FORWARDER
from config.constants import ETH_DIGG_BTC_CHAINLINK
from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import SUSHI_DIGG_WBTC
from config.constants import SUSHI_SUBGRAPH
from config.constants import UNIV2_DIGG_WBTC
from config.constants import UNI_SUBGRAPH
from config.enums import Network
from src.tx_utils import get_effective_gas_price
from src.tx_utils import get_gas_price_of_tx
from src.tx_utils import get_priority_fee
from src.web3_utils import confirm_transaction
from src.utils import get_abi
from src.utils import get_hash_from_failed_tx_error
from src.utils import send_oracle_error_to_discord
from src.utils import send_success_to_discord

# push report to centralizedOracle
REPORT_TIME_UTC = {"hour": 18, "minute": 30, "second": 0, "microsecond": 0}
GAS_LIMIT = 200_000
NEGATIVE_THRESHOLD = 0.95


class Oracle:
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger(__name__)
        self.web3 = Web3(Web3.HTTPProvider(web3))
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_ETH_USD_CHAINLINK),
            abi=get_abi(Network.Ethereum, "oracle"),
        )
        self.centralized_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(DIGG_CENTRALIZED_ORACLE),
            abi=get_abi(Network.Ethereum, "digg_centralized_oracle"),
        )
        self.chainlink_forwarder = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(DIGG_CHAINLINK_FORWARDER),
            abi=get_abi(Network.Ethereum, "chainlink_forwarder"),
        )
        self.digg_btc_chainlink = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_DIGG_BTC_CHAINLINK),
            abi=get_abi(Network.Ethereum, "oracle"),
        )

    def is_negative_rebase(self):
        price = self.digg_btc_chainlink.functions.latestAnswer().call()
        self.logger.info(f"price: [{price} - {price / 10 ** 8}]")
        return price / 10 ** 8 < NEGATIVE_THRESHOLD

    def propose_centralized_report_push(self):
        """Gets price using centralized oracle and pushes report to market oracle for use
        in rebase calculation.

        Args:
            oracle (str): name of oracle to use to push report
        """
        digg_twap = self.get_digg_twap_centralized()

        self.__process_centralized_oracle_tx(digg_twap, "Propose")

    def approve_centralized_report_push(self):
        """Gets price using selected oracle and pushes report to market oracle for use
        in rebase calculation.

        Args:
            oracle (str): name of oracle to use to push report
        """
        digg_twap = self.get_digg_twap_centralized()

        self.__process_centralized_oracle_tx(digg_twap, "Approve")

    def __process_centralized_oracle_tx(self, price: int, function: str):
        """Private function to create, broadcast, confirm centralized oracle tx on eth and then send
        transaction to Discord for monitoring
        """
        try:
            tx_hash = self.__send_centralized_oracle_tx(price, function)
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.eth_usd_oracle, tx_hash, Network.Ethereum
                )
                self.logger.info(f"got gas price of tx: ${gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Centralized Oracle {function}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type=f"Centralized Oracle {function}", tx_hash=tx_hash
                )
        except Exception as e:
            self.logger.error(f"Error processing oracle tx: {e}")
            send_oracle_error_to_discord(
                tx_type=f"Centralized Oracle {function}", error=e
            )

    def __send_centralized_oracle_tx(self, price: int, function: str) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            priority_fee = get_priority_fee(self.web3)
            self.logger.info(f"priority_fee: {priority_fee}")
            options = {
                "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
                "from": self.keeper_address,
                "maxPriorityFeePerGas": priority_fee,
                "maxFeePerGas": get_effective_gas_price(self.web3),
                "gas": GAS_LIMIT,
            }

            if function == "Propose":
                tx = self.centralized_oracle.functions.proposeReport(
                    price
                ).buildTransaction(options)
            elif function == "Approve":
                tx = self.centralized_oracle.functions.approveReport(
                    price
                ).buildTransaction(options)

            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

        except ValueError as e:
            self.logger.error(f"Error in sending oracle tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, self.logger, keeper_address=self.keeper_address
            )
        except Exception as e:
            self.logger.error(format_exc())
            tx_hash = get_hash_from_failed_tx_error(
                e, self.logger, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash

    def get_digg_twap_centralized(self) -> int:
        """Calculates 24 hour TWAP for digg based on sushi and uni wbtc / digg pools

        Returns:
            [int]: average of 24 hour TWAP for sushi and
            uni wbtc / digg pools time 10^18 (digg decimal places)
        """

        uni_twap_data = self.send_twap_query("uni", UNI_SUBGRAPH, UNIV2_DIGG_WBTC)
        sushi_twap_data = self.send_twap_query("sushi", SUSHI_SUBGRAPH, SUSHI_DIGG_WBTC)

        uni_prices = [
            float(x["reserve0"]) / float(x["reserve1"])
            for x in uni_twap_data["data"]["pairHourDatas"]
        ]
        sushi_prices = [
            float(x["reserve0"]) / float(x["reserve1"])
            for x in sushi_twap_data["data"]["pairHourDatas"]
        ]

        uni_twap = sum(uni_prices) / len(uni_prices)
        sushi_twap = sum(sushi_prices) / len(sushi_prices)
        avg_twap = (uni_twap + sushi_twap) / 2
        self.logger.info(f"24 Hour Uniswap TWAP: {uni_twap}")
        self.logger.info(f"24 Hour Sushiswap TWAP: {sushi_twap}")
        self.logger.info(f"Average TWAP: {avg_twap}")

        return int(avg_twap * 10 ** 18)

    def send_twap_query(self, exchange: str, url: str, pair: str) -> dict:
        """Builds and sends query to selected subgraph to retrieve the prices of the given
        pair every hour over the past 24 hours.

        Args:
            url (str): subgraph api url
            pair (str): ethereum address of LP pair for use in subgraph query

        Returns:
            [dict]: json return from subgraph api call to LP for price per hour for every
            hour in past 24.
        """

        today = self._get_today_report_datetime()
        yesterday = today.replace(day=today.day - 1)

        today_timestamp = round(today.timestamp())
        yesterday_timestamp = round(yesterday.timestamp())
        time_id = "hourStartUnix" if exchange == "uni" else "date"

        query = f"""
        {{
            pairHourDatas(where:
                {{
                pair: \"{pair}\"
                {time_id}_gte: {yesterday_timestamp}
                {time_id}_lte: {today_timestamp}
                }}
            )
            {{
                id
                {time_id}
                reserve0
                reserve1
            }}
        }}
        """

        r = requests.post(url, json={"query": query})
        return json.loads(r.content)

    def _get_today_report_datetime(self):
        """Generates the end time datetime object for the oracle report to use in its query.
        Uses the time set in REPORT_TIME_UTC constant dict. For instance if the REPORT_TIME_UTC
        dict is:

        {
            "hour": 19,
            "minute": 0,
            "second": 0,
            "microsecond": 0
        }

        Then the method will return the datetime object representing 19:00:00.00 in UTC time for
        the current date.

        Returns:
            [datetime]: datetime object representing the end time for the TWAP report
        """
        today = datetime.now(timezone.utc)
        today = today.replace(
            hour=REPORT_TIME_UTC.get("hour"),
            minute=REPORT_TIME_UTC.get("minute"),
            second=REPORT_TIME_UTC.get("second"),
            microsecond=REPORT_TIME_UTC.get("microsecond"),
        )
        return today

    def get_digg_twap_uma(self) -> float:
        return 0

    def publish_chainlink_report(self):
        self.__process_chainlink_tx()

    def __process_chainlink_tx(self):
        """Private function to create, broadcast, confirm centralized oracle tx on eth and then send
        transaction to Discord for monitoring
        """
        try:
            tx_hash = self.__send_chainlink_tx()
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.eth_usd_oracle, tx_hash, Network.Ethereum
                )
                self.logger.info(f"got gas price of tx: ${gas_price_of_tx}")
                send_success_to_discord(
                    tx_type="Chainlink Forwarder",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(tx_type="Chainlink Forwarder", tx_hash=tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing chainlink tx: {e}")
            send_oracle_error_to_discord(tx_type="Chainlink Forwarder", error=e)

    def __send_chainlink_tx(self) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            priority_fee = get_priority_fee(self.web3)
            self.logger.info(f"priority_fee: {priority_fee}")
            options = {
                "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
                "from": self.keeper_address,
                "maxPriorityFeePerGas": priority_fee,
                "maxFeePerGas": get_effective_gas_price(self.web3),
                "gas": GAS_LIMIT,
            }
            tx = self.chainlink_forwarder.functions.getThePrice().buildTransaction(
                options
            )

            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

        except ValueError as e:
            self.logger.error(f"Error in sending chainlink tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, self.logger, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash
