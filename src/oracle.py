from datetime import datetime, timezone
from hexbytes import HexBytes
import json
import logging
import os
import requests
import sys
from web3 import Web3, contract, exceptions

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

# push report to centralizedOracle
REPORT_TIME_UTC = {"hour": 19, "minute": 0, "second": 0, "microsecond": 0}
WETH_ADDRESS = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


class Oracle:
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger("oracle")
        self.web3 = Web3(Web3.HTTPProvider(web3))  # get secret here
        self.keeper_key = keeper_key  # get secret here
        self.keeper_address = keeper_address  # get secret here
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("ETH_USD_CHAINLINK")),
            abi=self.__get_abi("oracle"),
        )

    def __get_abi(self, contract_id: str):
        with open(f"./abi/eth/{contract_id}.json") as f:
            return json.load(f)

    def push_report(self, oracle: str):
        """Gets price using selected oracle and pushes report to market oracle for use
        in rebase calculation.

        Args:
            oracle (str): name of oracle to use to push report
        """
        if oracle == "centralized":
            digg_twap = self.get_digg_twap_centralized()
        elif oracle == "uma":
            digg_twap = self.get_digg_twap_uma()
        # centralizedMulti = GnosisSafe(digg.centralizedOracle)

        # tx = centralizedMulti.execute(
        #     MultisigTxMetadata(description="Set Market Data"),
        #     {
        #         "to": digg.marketMedianOracle.address,
        #         "data": digg.marketMedianOracle.pushReport.encode_input(marketValue),
        #     },
        # )

        # # execute
        # self.transactions.append(MultisigTx(params, metadata))
        # # multisigTx
        # # self.params = params
        # # self.metadata = metadata
        # id = len(self.transactions) - 1
        # return self.executeTx(id)

        # # executeTx
        # tx = None
        # if not id:
        #     tx = self.transactions[-1]
        # else:
        #     tx = self.transactions[id]

        # if print_output:
        #     self.printTx(id)

        pass

    def get_digg_twap_centralized(self) -> float:
        """Calculates 24 hour TWAP for digg based on sushi and uni wbtc / digg pools

        Returns:
            [float]: average of 24 hour TWAP for sushi and uni wbtc / digg pools
        """

        uni_twap_data = self.send_twap_query(
            os.getenv("UNI_SUBGRAPH"), os.getenv("UNI_PAIR")
        )
        sushi_twap_data = self.send_twap_query(
            os.getenv("SUSHI_SUBGRAPH"), os.getenv("SUSHI_PAIR")
        )

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
        self.logger.info(f"24 Hour Uniswap TWAP: {uni_twap}")
        self.logger.info(f"24 Hour Sushiswap TWAP: {sushi_twap}")

        return (uni_twap + sushi_twap) / 2

    def send_twap_query(self, url: str, pair: str) -> dict:
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

        query = f"""
        {{ 
            pairHourDatas(where: 
                {{
                pair: \"{pair}\"
                hourStartUnix_gte: {yesterday_timestamp}
                hourStartUnix_lte: {today_timestamp}
                }}
            ) 
            {{ 
                id 
                hourStartUnix 
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

    def request_uma_report(self):
        price_identifier = "DIGGBTC".encode("utf-8")
        today_timestamp = round(self._get_today_report_datetime().timestamp())
        ancillary_data = HexBytes(0)
        currency = WETH_ADDRESS
        reward = 0

        """
        function requestPrice(
            bytes32 identifier,
            uint256 timestamp,
            bytes memory ancillaryData,
            IERC20 currency,
            uint256 reward
        ) external virtual returns (uint256 totalBond);
        """
        pass

    def get_digg_twap_uma(self) -> float:
        return 0
