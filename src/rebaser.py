import datetime
from enum import Enum
import json
import logging
import os
import time
from utils import get_secret, hours
import warnings
from web3 import Web3, contract, exceptions

import brownie
import requests

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
DIGG_TOKEN_ADDRESS = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
DIGG_ORCHESTRATOR_ADDRESS = "0xbd5d9451e004fc495f105ceab40d6c955e4192ba"
DIGG_POLICY_ADDRESS = "0x327a78D13eA74145cc0C63E6133D516ad3E974c3"
CPI_MEDIAN_ORACLE_ADDRESS = "0xEd57725991983E407837CE4B3e0F0fa38bd161B6"
UNIV2_DIGG_WBTC_ADDRESS = "0xe86204c4eddd2f70ee00ead6805f917671f56c52"
SUSHI_DIGG_WBTC_ADDRESS = "0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3"

class Rebaser():
    def __init__(
        self,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        web3=Web3(Web3.HTTPProvider(os.getenv("ETH_NODE_URL"))),
    ):
        self.logger = logging.getLogger()
        self.web3 = web3 # get secret here
        self.keeper_key = keeper_key # get secret here
        self.keeper_address = keeper_address # get secret here
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(ETH_USD_CHAINLINK),
            abi=self.__get_abi("oracle"),
        )
        self.digg_token = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("DIGG_TOKEN_ADDRESS")),
            abi=self.__get_abi("digg_token")
        )
        self.digg_orchestrator = self.web3.eth.contract(
            address=DIGG_ORCHESTRATOR_ADDRESS,
            abi=self.__get_abi("digg_orchestrator")
        )
        self.digg_policy = self.web3.eth.contract(
            address=DIGG_POLICY_ADDRESS,
            abi=self.__get_abi("digg_policy")
        )
        # TODO: create oracle interface that abstracts which oracle we use away from rebaser
        # should be able to switch or update oracles and not impact this class.
        self.cpi_median_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("CPI_MEDIAN_ORACLE_ADDRESS")),
            abi=self.__get_abi("digg_cpi_median_oracle")
        )
        self.uni_pair = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("UNIV2_DIGG_WBTC_ADDRESS")),
            abi=self.__get_abi("univ2_pair")
        )
        self.sushi_pair = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.getenv("SUSHI_DIGG_WBTC_ADDRESS")),
            abi=self.__get_abi("sushi_pair")
        )
    
    def __get_abi(self, contract_id: str):
        with open(f"./abi/eth/{contract_id}.json") as f:
            return json.load(f)

    def rebase(self, account):
        # get supply
        supply_before = self.digg_token.functions.totalSupply().call()
        spf_before = self.digg_token.functions._sharesPerFragment().call()

        self.logger.info(f"spf before: {spf_before}")
        self.logger.info(f"supply before: {supply_before}")

        # log oracle info
        self.logger.info(self.cpi_median_oracle.functions.getData().call())

        # call digg cuntions
        last_rebase_time = self.digg_policy.functions.lastRebaseTimestampSec().call()
        min_rebase_time = self.digg_policy.functions.minRebaseTimeIntervalSec().call()
        in_rebase_window = self.digg_policy.functions.inRebaseWindow().call()
        # can use time.now()
        now = time.time()

        time_since_last_rebase = now - last_rebase_time
        min_time_passed = (last_rebase_time + min_rebase_time) < now

        self.logger.info({
            "last_rebase_time": last_rebase_time,
            "in_rebase_window": in_rebase_window,
            "now": now,
            "time_since_last_rebase": time_since_last_rebase,
            "min_time_passed": min_time_passed,
        })

        # Rebase if sufficient time has passed since last rebase and we are in the window.
        # Give adequate time between TX attempts
        if (time_since_last_rebase > hours(2) and in_rebase_window and min_time_passed):
            self.logger.info("[bold yellow]===== 📈 Rebase! 📉=====[/bold yellow]")
            sushi_reserves = self.sushi_pair.functions.getReserves().call()
            uni_reserves = self.uni_pair.functions.getReserves().call()
            self.logger.info(f"sushi pair before: {sushi_reserves}")
            self.logger.info(f"uni pair before: {uni_reserves}")

            #tx_timer.start_timer(account, 'Rebase')
            tx = self.digg_orchestrator.functions.rebase({"from": account}).call()
            #tx_timer.end_timer()

            # if rpc.is_active():
            #     chain.mine()
            #     self.logger.info(tx.call_trace())
            #     self.logger.info(tx.events)

            supply_after = self.digg_token.functions.totalSupply().call()
            spf_after = self.digg_token.functions._sharesPerFragment().call()

            sushi_reserves = self.sushi_pair.functions.getReserves().call()
            uni_reserves = self.uni_pair.functions.getReserves().call()

            self.logger.info(f"spfAfter: {spf_after}")
            self.logger.info(f"supply after: {supply_after}")
            self.logger.info(f"supply change: {supply_after / supply_before}")
            self.logger.info(f"supply change other way: {supply_before / supply_after}")

            self.logger.info(f"sushi reserves after {sushi_reserves}")
            self.logger.info(f"uni reserves after: {uni_reserves}")
        else:
            self.logger.info("[white]===== No Rebase =====[/white]")