import logging
import os
import requests
import sys
from decimal import Decimal
from hexbytes import HexBytes
from time import sleep
from web3 import Web3, contract, exceptions

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./data_classes"))
)
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from emissions_schedule import EmissionsSchedule
from constants import (
    MULTICHAIN_CONFIG,
    THREE_DAYS_OF_BLOCKS,
    DAYS_IN_WEEK,
    BADGER_TOKEN,
    DIGG_TOKEN,
)
from utils import (
    confirm_transaction,
    hours,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
    get_hash_from_failed_tx_error,
    get_last_harvest_times,
    get_rewards_schedule,
    get_last_external_harvest_times,
    to_digg_shares_and_fragments,
)
from tx_utils import get_priority_fee, get_effective_gas_price, get_gas_price_of_tx

logging.basicConfig(level=logging.INFO)

MAX_TIME_BETWEEN_HARVESTS = hours(71)  # 71 hours
SECONDS_IN_A_DAY = 60 * 60 * 24

GAS_LIMITS = {
    "eth": 6_000_000,
    "poly": 1_000_000,
    "arbitrum": 3_000_000,
}
NUM_FLASHBOTS_BUNDLES = 6
API_PARAMS = {
    "eth": {"currency": "eth", "chain": "eth"},
    "poly": {"currency": "matic", "chain": "matic"},
    "arbitrum": {"currency": "eth", "chain": "arbitrum"},
}


class ExternalHarvester:
    def __init__(
        self,
        web3: Web3,
        chain: str = "eth",  # TODO: Identify chain from web3.eth.chain_id (single source of truth)
        keeper_address: str = os.getenv("KEEPER_ADDRESS"),
        keeper_key: str = os.getenv("KEEPER_KEY"),
        base_oracle_address: str = os.getenv("ETH_USD_CHAINLINK"),
        use_flashbots: bool = False,
        discord_url: str = None,
    ):
        self.logger = logging.getLogger("harvester")
        self.chain = chain
        self.web3 = web3
        self.keeper_key = keeper_key
        self.keeper_address = keeper_address
        self.keeper_acl = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(
                MULTICHAIN_CONFIG[self.chain]["rewards_manager"]
            ),
            abi=get_abi(self.chain, "rewards_manager"),
        )
        self.base_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(base_oracle_address),
            abi=get_abi(self.chain, "oracle"),
        )
        self.config = MULTICHAIN_CONFIG[self.chain]["external_harvest"]
        # TODO: figure this out for ext harvest Times of last harvest
        self.last_harvest_times = get_last_external_harvest_times(
            self.web3,
            self.keeper_acl,
            start_block=self.web3.eth.block_number - THREE_DAYS_OF_BLOCKS * 10,
        )
        schedule_json = get_rewards_schedule()
        self.emissions = EmissionsSchedule(schedule_json)
        self.schedule = self.emissions.get_schedule()

        self.use_flashbots = use_flashbots
        self.discord_url = discord_url

    def is_time_to_harvest(
        self,
        strategy: contract,
        harvest_interval_threshold: int = MAX_TIME_BETWEEN_HARVESTS,
    ) -> bool:
        """Calculates the time between harvests for the supplied strategy and returns true if
        it has been longer than the supplied harvest_interval_threshold which is measured in seconds.

        Args:
            strategy (contract): Vault strategy web3 contract object
            harvest_interval_threshold (int, optional): Amount of time in seconds that is acceptable to not
                have harvested within. Defaults to MAX_TIME_BETWEEN_HARVESTS (71 hours in seconds).

        Returns:
            bool: True if time since last harvest is > harvest_interval_threshold, else False
        """
        # Only care about harvest gas costs on eth
        if self.chain != "eth":
            return True

        try:
            last_harvest = self.last_harvest_times[strategy.address]
            current_time = self.web3.eth.get_block("latest")["timestamp"]

            return current_time - last_harvest > harvest_interval_threshold
        except KeyError:
            return True

    def days_since_last_harvest(self, strategy_addr: str) -> int:
        last_harvest = self.last_harvest_times[strategy_addr]
        current_time = self.web3.eth.get_block("latest")["timestamp"]

        return round((current_time - last_harvest) / SECONDS_IN_A_DAY)

    def harvest_single_assets(
        self,
    ):
        for strategy_addr in self.config["single_asset"]["strategies"]:
            strategy = self.web3.eth.contract(
                address=strategy_addr,
                abi=get_abi(self.chain, "strategy"),
            )
            strategy_name = strategy.functions.getName().call()

            if not self.__is_keeper_whitelisted(strategy):
                raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

            days_since_last = self.days_since_last_harvest(strategy_addr)
            if days_since_last > 0:
                last_timestamp = self.last_harvest_times[strategy_addr]

                amount_badger_owed = self.get_amount_badger_owed(
                    last_timestamp, strategy_addr
                )
                amount_digg_owed = self.get_amount_digg_owed(
                    last_timestamp, strategy_addr
                )
                if amount_badger_owed > 0:
                    # distribue
                    self.__process_transfer_want(
                        strategy=strategy,
                        strategy_name=strategy_name,
                        token_address=BADGER_TOKEN,
                        amount=amount_badger_owed,
                    )
                    sleep(30)
                if amount_digg_owed > 0:
                    # distribute
                    self.__process_transfer_want(
                        strategy=strategy,
                        strategy_name=strategy_name,
                        token_address=DIGG_TOKEN,
                        amount=amount_badger_owed,
                    )
                    sleep(30)

    def get_amount_badger_owed(self, last_timestamp: int, vault_address: str) -> int:
        total_amount = 0
        current_time = self.web3.eth.get_block("latest")["timestamp"]

        days_elapsed = (current_time - last_timestamp) // SECONDS_IN_A_DAY
        if days_elapsed == 0:
            return total_amount

        self.logger.info(f"Getting badger owed over last {days_elapsed} days")
        weeks_to_check = self._get_weekly_start_times(last_timestamp, current_time)

        schedules_and_days_elapsed = self._num_days_per_week(
            weeks_to_check, last_timestamp, current_time
        )
        # [(key_for_schedule, days_to_distribute)]

        for week in schedules_and_days_elapsed:
            key = week[0]
            days = week[1]
            self.logger.info(f"schedule {key} distribute for {days} days")
            total_amount += self._get_amount_badger(key, days, vault_address)

        sum_of_days = sum([x[1] for x in schedules_and_days_elapsed])
        self.logger.info(f"distributing rewards over {sum_of_days}")
        return total_amount

    def get_amount_digg_owed(self, last_timestamp: int, vault_address: str) -> int:
        total_amount = 0
        current_time = self.web3.eth.get_block("latest")["timestamp"]

        days_elapsed = (current_time - last_timestamp) // SECONDS_IN_A_DAY
        if days_elapsed == 0:
            return total_amount

        self.logger.info(f"Getting digg owed over last {days_elapsed} days")
        weeks_to_check = self._get_weekly_start_times(last_timestamp, current_time)

        schedules_and_days_elapsed = self._num_days_per_week(
            weeks_to_check, last_timestamp, current_time
        )
        # [(key_for_schedule, days_to_distribute)]

        for week in schedules_and_days_elapsed:
            key = week[0]
            days = week[1]
            self.logger.info(f"in {key} distribute for {days} days")
            total_amount += self._get_amount_digg(key, days, vault_address)

        sum_of_days = sum([x[1] for x in schedules_and_days_elapsed])
        self.logger.info(f"distributing rewards over {sum_of_days}")
        return total_amount

    def _get_weekly_start_times(self, last_timestamp: int, current_time: int) -> list:
        """[summary]

        Args:
            last_timestamp (int): timestamp of last distribution
            current_time (int): current timestamp

        Returns:
            list: keys to self.schedule of the rewards schedules to be used in distribution
        """
        weeks = []
        for start_time in self.schedule.keys():
            start_time = int(start_time)
            if start_time > last_timestamp and start_time <= current_time:
                weeks.append(str(start_time))

        return weeks

    def _num_days_per_week(
        self, weeks_to_check: list, last_timestamp: int, current_time: int
    ) -> list:
        """Returns a list of all of the weekly emissions schedules' dictionary keys that need to be
        used to calculate how many rewards should be distributed alongside how many days of that week's
        schedule need to be accounted for.

        Args:
            weeks_to_check (list): timestamp keys of schedule dict that need to be looked at for rewards
            last_timestamp (int): the last timestamp a distribution occurred
            current_time (int): the current timestamp

        Returns:
            list: tuples representing the key for that weeks schedule and the number of days to distribute

            Ex. the list [("1630602000", 2), ("1631206800", 3)] would mean we need to distribute 2 days
            of rewards using the emissions schedule starting at 1630602000 and 3 days of rewards using
            the emissions schedule starting at 1631206800.
        """
        if weeks_to_check == []:
            days_elapsed_previous = (current_time - last_timestamp) // SECONDS_IN_A_DAY
        else:
            days_elapsed_previous = (
                int(weeks_to_check[0]) - last_timestamp
            ) // SECONDS_IN_A_DAY

        # need to check the previous weeks schedule in case we haven't distributed for all 7 days yet
        previous_time = 0
        for start_time in self.schedule.keys():
            if current_time < int(start_time) and current_time >= int(previous_time):
                break
            previous_time = start_time
        previous_schedule_start = previous_time

        distribution = []
        weekly_rewards = (previous_schedule_start, days_elapsed_previous)
        distribution.append(weekly_rewards)

        # for each week get num of days to distribute, can max distribute 7 days
        for week in weeks_to_check:
            duration = (int(current_time) - int(week)) // SECONDS_IN_A_DAY
            weekly_rewards = (week, min(7, duration))
            distribution.append(weekly_rewards)

        return distribution

    def _get_amount_badger(self, key: str, days: int, address: str) -> int:
        emissions_for_week = self.schedule[key]

        amount_per_week = emissions_for_week[address]["badger_allocation"]
        self.logger.info(f"weekly allotment badger: {amount_per_week}")

        amount_badger = amount_per_week * days / DAYS_IN_WEEK
        self.logger.info(f"amount badger: {amount_badger}")
        return amount_badger

    def _get_amount_digg(self, key: str, days: int, address: str) -> int:
        emissions_for_week = self.schedule[key]

        amount_per_week = emissions_for_week[address]["digg_allocation"]
        self.logger.info(f"weekly allotment digg: {amount_per_week}")

        amount_digg = amount_per_week * days / DAYS_IN_WEEK
        self.logger.info(f"amount digg: {amount_digg}")

        return amount_digg

    def __is_keeper_whitelisted(self, strategy: contract) -> bool:
        """Checks if the bot we're using is whitelisted for the strategy.

        Args:
            strategy (contract)

        Returns:
            bool: True if our bot is whitelisted to make function calls to strategy,
            False otherwise.
        """
        key = self.keeper_acl.functions.KEEPER_ROLE().call()
        return self.keeper_acl.functions.hasRole(key, self.keeper_address).call()

    def __process_transfer_want(
        self,
        strategy: contract = None,
        strategy_name: str = None,
        token_address: str = None,
        amount: int = 0,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            strategy (contract, optional): Defaults to None.
            strategy_name (str, optional): Defaults to None.
            harvested (Decimal, optional): Amount of Sushi harvested. Defaults to None.
        """
        try:
            tx_hash, max_target_block = self.__send_transfer_want_tx(
                strategy, token_address=token_address, amount=amount
            )
            succeeded, msg = confirm_transaction(
                self.web3, tx_hash, max_block=max_target_block
            )
            if succeeded:
                # If successful, update last harvest harvest time to make sure we don't double harvest
                self.update_last_harvest_time(strategy.address)
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
                self.logger.info(f"got gas price of tx: {gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Transfer Want {strategy_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                    url=self.discord_url,
                )
            elif tx_hash != HexBytes(0):
                if not self.use_flashbots:
                    # And if pending
                    self.update_last_harvest_time(strategy.address)
                    send_success_to_discord(
                        tx_type=f"Transfer Want {strategy_name}",
                        tx_hash=tx_hash,
                        chain=self.chain,
                        url=self.discord_url,
                    )
                else:
                    send_error_to_discord(
                        strategy_name, "Transfer Want", tx_hash=tx_hash, message=msg
                    )
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            send_error_to_discord(strategy_name, "Transfer Want", error=e)

    def __send_transfer_want_tx(
        self, strategy: contract, token_address: str = None, amount: int = 0
    ) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            strategy (contract)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        max_target_block = None
        tx_hash = HexBytes(0)
        try:
            tx = self.__build_transfer_want_tx(
                strategy.address, token_address=token_address, amount=amount
            )
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = signed_tx.hash

            if not self.use_flashbots:
                self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            else:
                bundle = [
                    {"signed_transaction": signed_tx.rawTransaction},
                ]

                block_number = self.web3.eth.block_number
                for i in range(1, NUM_FLASHBOTS_BUNDLES + 1):
                    self.web3.flashbots.send_bundle(
                        bundle, target_block_number=block_number + i
                    )
                max_target_block = block_number + NUM_FLASHBOTS_BUNDLES
                self.logger.info(f"Bundle broadcasted at {max_target_block}")

        except ValueError as e:
            self.logger.error(f"Error in sending harvest tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(e, "Harvest")
        finally:
            return tx_hash, max_target_block

    def __build_transfer_want_tx(
        self,
        strategy_address: str,
        token_address: str,
        amount: int,
    ) -> dict:
        """Builds transaction depending on which chain we're harvesting. EIP-1559
        requires different handling for ETH txs than the other EVM chains.

        Args:
            contract (contract): contract to use to build tx

        Returns:
            dict: tx dictionary
        """
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
            "gas": GAS_LIMITS[self.chain],
        }
        if self.chain == "eth":
            options["maxPriorityFeePerGas"] = get_priority_fee(self.web3)
            options["maxFeePerGas"] = get_effective_gas_price(self.web3)
        else:
            options["gasPrice"] = get_effective_gas_price(self.web3)

        self.logger.info(
            f"estimated gas fee: {self.__estimate_transfer_want_gas(strategy_address, token_address, amount)}"
        )
        return self.keeper_acl.functions.transferWant(
            token_address, strategy_address, amount
        ).buildTransaction(options)

    def __estimate_transfer_want_gas(
        self, strategy_address: str, token_address: str, amount: int
    ) -> Decimal:
        estimated_gas = self.keeper_acl.functions.transferWant(
            token_address, strategy_address, amount
        ).estimateGas({"from": self.keeper_address})

        return Decimal(estimated_gas)

    def update_last_harvest_time(self, strategy_address: str):
        self.last_harvest_times[strategy_address] = self.web3.eth.get_block("latest")[
            "timestamp"
        ]
