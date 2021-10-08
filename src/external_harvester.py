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
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from constants import MULTICHAIN_CONFIG, THREE_DAYS_OF_BLOCKS
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
            start_block=self.web3.eth.block_number - THREE_DAYS_OF_BLOCKS,
        )
        self.rewards_schedule = get_rewards_schedule()

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

    def get_badger_amount_owed(self, last_timestamp: int, strategy_addr: str) -> int:
        return 1

    def get_digg_amount_owed(self, last_timestamp: int, strategy_addr: str) -> int:
        return 1

    def get_amount_to_transfer(self, strategy_addr: str, days_since_last: int) -> int:

        return 1

    def harvest_single_assets(
        self,
    ):
        for strategy_addr in self.config["single_asset"]["strategies"]:
            days_since_last = self.days_since_last_harvest(strategy_addr)
            if days_since_last > 0:
                # get last harvest timestamp
                last_timestamp = self.last_harvest_times[strategy_addr]

                # calculate amount of badger owed since last harvest
                amount_badger_owed = self.get_amount_badger_owed(
                    last_timestamp, strategy_addr
                )
                # calculate amount of digg owed since last harvest
                amount_digg_owed = self.get_amount_digg_owed(
                    last_timestamp, strategy_addr
                )

                if amount_badger_owed > 0:
                    # distribue
                    sleep(30)

                if amount_digg_owed > 0:
                    # distribute
                    sleep(30)
                # if lp, swap and distribute
                # else just distribute
                strategy = self.keeper_acl = self.web3.eth.contract(
                    address=strategy_addr,
                    abi=get_abi(self.chain, "strategy"),
                )
                strategy_name = strategy.functions.getName().call()

                if not self.__is_keeper_whitelisted(strategy):
                    raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

                amount_to_transfer = self.get_amount_to_transfer(
                    strategy_addr, days_since_last
                )

                gas_fee = self.estimate_gas_fee(strategy.address)
                self.logger.info(f"estimated gas cost: {gas_fee}")

                self.__process_harvest(
                    strategy=strategy,
                    strategy_name=strategy_name,
                )

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

    def __process_harvest(
        self,
        strategy: contract = None,
        strategy_name: str = None,
        harvested: Decimal = None,
        returns: bool = True,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            strategy (contract, optional): Defaults to None.
            strategy_name (str, optional): Defaults to None.
            harvested (Decimal, optional): Amount of Sushi harvested. Defaults to None.
        """
        try:
            tx_hash, max_target_block = self.__send_harvest_tx(
                strategy, returns=returns
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
                    tx_type=f"Harvest {strategy_name}",
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
                        tx_type=f"Harvest {strategy_name}",
                        tx_hash=tx_hash,
                        chain=self.chain,
                        url=self.discord_url,
                    )
                else:
                    send_error_to_discord(
                        strategy_name, "Harvest", tx_hash=tx_hash, message=msg
                    )
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            send_error_to_discord(strategy_name, "Harvest", error=e)

    def __send_harvest_tx(self, strategy: contract, returns: bool = True) -> HexBytes:
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
            tx = self.__build_transaction(strategy.address, returns=returns)
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

    def __build_transaction(
        self, strategy_address: str, returns: bool = True, function: str = "harvest"
    ) -> dict:
        """Builds transaction depending on which chain we're harvesting. EIP-1559
        requires different handling for ETH txs than the other EVM chains.

        Args:
            contract (contract): contract to use to build harvest tx

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
            options["maxFeePerGas"] = self.__get_effective_gas_price()
        else:
            options["gasPrice"] = self.__get_effective_gas_price()

        if function == "harvest":
            self.logger.info(
                f"estimated gas fee: {self.__estimate_harvest_gas(strategy_address, returns)}"
            )
            return self.__build_harvest_transaction(strategy_address, returns, options)

    def __build_harvest_transaction(
        self, strategy_address: str, returns: bool, options: dict
    ) -> dict:
        if returns:
            return self.keeper_acl.functions.harvest(strategy_address).buildTransaction(
                options
            )
        else:
            return self.keeper_acl.functions.harvestNoReturn(
                strategy_address
            ).buildTransaction(options)

    def estimate_gas_fee(
        self, strategy_address: str, returns: bool = True, function: str = "harvest"
    ) -> Decimal:
        current_gas_price = self.__get_effective_gas_price()
        if function == "harvest":
            estimated_gas = self.__estimate_harvest_gas(strategy_address, returns)
        elif function == "tend":
            estimated_gas = self.__estimate_tend_gas(strategy_address)

        return Decimal(current_gas_price * estimated_gas)

    def __estimate_harvest_gas(self, strategy_address: str, returns: bool) -> Decimal:
        if returns:
            estimated_gas_to_harvest = self.keeper_acl.functions.harvest(
                strategy_address
            ).estimateGas({"from": self.keeper_address})
        else:
            estimated_gas_to_harvest = self.keeper_acl.functions.harvestNoReturn(
                strategy_address
            ).estimateGas({"from": self.keeper_address})

        return Decimal(estimated_gas_to_harvest)

    def __estimate_tend_gas(self, strategy_address: str) -> Decimal:
        return Decimal(
            self.keeper_acl.functions.tend(strategy_address).estimateGas(
                {"from": self.keeper_address}
            )
        )

    def __get_effective_gas_price(self) -> int:
        if self.chain == "poly":
            response = requests.get("https://gasstation-mainnet.matic.network").json()
            gas_price = self.web3.toWei(int(response.get("fast") * 1.1), "gwei")
        elif self.chain == "arbitrum":
            gas_price = int(1.1 * self.web3.eth.gas_price)
            # Estimated gas price + buffer
        elif self.chain == "eth":
            # EIP-1559
            gas_price = get_effective_gas_price(self.web3)
        return gas_price

    def update_last_harvest_time(self, strategy_address: str):
        self.last_harvest_times[strategy_address] = self.web3.eth.get_block("latest")[
            "timestamp"
        ]