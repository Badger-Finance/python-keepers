from datetime import datetime, timezone
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
SUSHI_SUBGRAPH = (
    "https://api.thegraph.com/subgraphs/name/dimitarnestorov/sushiswap-subgraph"
)
UNI_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
SUSHI_PAIR = "0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3"
UNI_PAIR = "0xe86204c4eddd2f70ee00ead6805f917671f56c52"
CENTRALIZED_ORACLE = "0x72dc16CFa95beB42aeebD2B10F22E55bD17Ce976"


class Oracle:
    def __init__(self):
        self.logger = logging.getLogger("oracle")

    def push_report(self):
        digg_twap = self.get_digg_twap()
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

    def get_digg_twap(self) -> float:
        """Calculates 24 hour TWAP for digg based on sushi and uni wbtc / digg pools

        Returns:
            [float]: average of 24 hour TWAP for sushi and uni wbtc / digg pools
        """

        uni_twap_data = self.send_twap_query(UNI_SUBGRAPH, UNI_PAIR)
        sushi_twap_data = self.send_twap_query(SUSHI_SUBGRAPH, SUSHI_PAIR)

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
        today = self._get_today_report_timestamp()
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

    def _get_today_report_timestamp(self):
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
