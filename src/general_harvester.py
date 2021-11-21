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

from constants import MULTICHAIN_CONFIG, BASE_CURRENCIES
from enums import Network, Currency
from harvester import IHarvester
from utils import (
    confirm_transaction,
    hours,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
    get_hash_from_failed_tx_error,
    get_last_harvest_times,
    seconds_to_blocks,
)
from tx_utils import get_priority_fee, get_effective_gas_price, get_gas_price_of_tx

logging.basicConfig(level=logging.INFO)

MAX_TIME_BETWEEN_HARVESTS = hours(120)
HARVEST_THRESHOLD = 0.0005  # min ratio of want to total vault AUM required to harvest

GAS_LIMITS = {
    Network.Ethereum: 6_000_000,
    Network.Polygon: 1_000_000,
    Network.Arbitrum: 3_000_000,
}
NUM_FLASHBOTS_BUNDLES = 6


class GeneralHarvester(IHarvester):
    def __init__(
        self,
        chain: str = Network.Ethereum,
        web3: Web3 = None,
        keeper_acl: str = os.getenv("KEEPER_ACL"),
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
            address=self.web3.toChecksumAddress(keeper_acl),
            abi=get_abi(self.chain, "keeper_acl"),
        )
        self.base_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(base_oracle_address),
            abi=get_abi(self.chain, "oracle"),
        )
        # Times of last harvest
        if self.chain == Network.Ethereum:
            self.last_harvest_times = get_last_harvest_times(
                self.web3,
                self.keeper_acl,
                start_block=self.web3.eth.block_number
                - seconds_to_blocks(MAX_TIME_BETWEEN_HARVESTS),
            )
        else:
            # Don't care about poly/arbitrum
            self.last_harvest_times = {}

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
                have harvested within. Defaults to MAX_TIME_BETWEEN_HARVESTS.

        Returns:
            bool: True if time since last harvest is > harvest_interval_threshold, else False
        """
        # Only care about harvest gas costs on eth
        if self.chain != Network.Ethereum:
            return True

        try:
            last_harvest = self.last_harvest_times[strategy.address]
            current_time = self.web3.eth.get_block("latest")["timestamp"]
            self.logger.info(
                f"Time since last harvest: {(current_time - last_harvest)/3600}"
            )

            return current_time - last_harvest > harvest_interval_threshold
        except KeyError:
            return True

    def harvest(
        self,
        strategy: contract,
    ):
        """Orchestration function that harvests outstanding rewards.

        Args:
            strategy (contract)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        strategy_name = strategy.functions.getName().call()

        # TODO: update for ACL
        if not self.__is_keeper_whitelisted("harvest"):
            raise ValueError(f"Keeper ACL is not whitelisted for calling harvest")

        want_address = strategy.functions.want().call()
        want = self.web3.eth.contract(
            address=want_address,
            abi=get_abi(self.chain, "erc20"),
        )
        vault_balance = want.functions.balanceOf(strategy.address).call()
        self.logger.info(f"vault balance: {vault_balance}")

        want_to_harvest = (
            self.estimate_harvest_amount(strategy)
            / 10 ** want.functions.decimals().call()
        )
        self.logger.info(f"estimated want change: {want_to_harvest}")

        # TODO: figure out how to handle profit estimation
        # current_price_eth = self.get_current_rewards_price()
        # self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy.address)
        self.logger.info(f"estimated gas cost: {gas_fee}")

        # for now we'll just harvest every hour
        should_harvest = self.is_profitable()
        self.logger.info(f"Should we harvest: {should_harvest}")

        if should_harvest:
            self.__process_harvest(
                strategy=strategy,
                strategy_name=strategy_name,
            )

    def harvest_no_return(
        self,
        strategy: contract,
    ):
        strategy_name = strategy.functions.getName().call()

        # TODO: update for ACL
        if not self.__is_keeper_whitelisted("harvestNoReturn"):
            raise ValueError(
                f"Keeper ACL is not whitelisted for calling harvestNoReturn"
            )

        want_address = strategy.functions.want().call()
        want = self.web3.eth.contract(
            address=want_address,
            abi=get_abi(self.chain, "erc20"),
        )
        vault_balance = want.functions.balanceOf(strategy.address).call()
        self.logger.info(f"vault balance: {vault_balance}")

        # TODO: figure out how to handle profit estimation
        # current_price_eth = self.get_current_rewards_price()
        # self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy.address, returns=False)
        self.logger.info(f"estimated gas cost: {gas_fee}")

        # for now we'll just harvest every hour
        should_harvest = self.is_profitable()
        self.logger.info(f"Should we harvest: {should_harvest}")

        if should_harvest:
            self.__process_harvest(
                strategy=strategy,
                strategy_name=strategy_name,
            )

    def harvest_rewards_manager(
        self,
        strategy: contract,
    ):
        strategy_name = strategy.functions.getName().call()

        self.keeper_acl = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(
                MULTICHAIN_CONFIG[self.chain]["rewards_manager"]
            ),
            abi=get_abi(self.chain, "rewards_manager"),
        )

        if not self.__is_keeper_whitelisted("rewards_manager"):
            raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

        want_address = strategy.functions.want().call()
        want = self.web3.eth.contract(
            address=want_address,
            abi=get_abi(self.chain, "erc20"),
        )
        vault_balance = want.functions.balanceOf(strategy.address).call()
        self.logger.info(f"vault balance: {vault_balance}")

        gas_fee = self.estimate_gas_fee(strategy.address)
        self.logger.info(f"estimated gas cost: {gas_fee}")

        self.__process_harvest(
            strategy=strategy,
            strategy_name=strategy_name,
        )

    def harvest_mta(
        self,
        voter_proxy: contract,
    ):
        # TODO: update for ACL
        if not self.__is_keeper_whitelisted("harvestMta"):
            raise ValueError(f"Keeper ACL is not whitelisted for calling harvestMta")

        gas_fee = self.estimate_gas_fee(voter_proxy.address, function="harvestMta")
        self.logger.info(f"estimated gas cost: {gas_fee}")

        should_harvest_mta = self.is_profitable()
        self.logger.info(f"Should we call harvestMta: {should_harvest_mta}")

        if should_harvest_mta:
            self.__process_harvest_mta(voter_proxy)

    def tend(self, strategy: contract):
        strategy_name = strategy.functions.getName().call()
        # TODO: update for ACL
        if not self.__is_keeper_whitelisted("tend"):
            raise ValueError(f"Keeper ACL is not whitelisted for calling tend")

        # TODO: figure out how to handle profit estimation
        # current_price_eth = self.get_current_rewards_price()
        # self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy.address, function="tend")
        self.logger.info(f"estimated gas cost: {gas_fee}")

        self.__process_tend(
            strategy=strategy,
            strategy_name=strategy_name,
        )

    def tend_then_harvest(self, strategy: contract):
        self.tend(strategy)
        sleep(60)
        self.harvest(strategy)

    def estimate_harvest_amount(self, strategy: contract) -> Decimal:
        want = self.web3.eth.contract(
            address=strategy.functions.want().call(),
            abi=get_abi(self.chain, "erc20"),
        )
        want_gained = self.keeper_acl.functions.harvest(strategy.address).call(
            {"from": self.keeper_address}
        )
        # call badger api to get prices
        currency = BASE_CURRENCIES[self.chain]
        chain = self.chain
        prices = requests.get(
            f"https://api.badger.finance/v2/prices?currency={currency}&chain={chain}"
        ).json()
        # Price of want token in ETH
        price_per_want = prices.get(want.address)
        self.logger.info(f"price per want: {price_per_want}")
        self.logger.info(f"want gained: {want_gained}")
        if type(want_gained) is list:
            want_gained = 0
        return price_per_want * want_gained

    def is_profitable(self) -> bool:
        # TODO: Implement this

        # harvest if ideal want change is > 0.05% of total vault assets
        # should_harvest = want_to_harvest / vault_balance >= HARVEST_THRESHOLD
        return True

    def __is_keeper_whitelisted(self, function: str) -> bool:
        """Checks if the bot we're using is whitelisted for the strategy.

        Returns:
            bool: True if our bot is whitelisted to make function calls, False otherwise.
        """
        if function in ["harvest", "harvestMta"]:
            key = self.keeper_acl.functions.HARVESTER_ROLE().call()
        elif function == "tend":
            key = self.keeper_acl.functions.TENDER_ROLE().call()
        elif function == "rewards_manager":
            key = self.keeper_acl.functions.KEEPER_ROLE().call()
        return self.keeper_acl.functions.hasRole(key, self.keeper_address).call()

    def __process_tend(
        self,
        strategy: contract = None,
        strategy_name: str = None,
    ):
        try:
            tx_hash = self.__send_tend_tx(strategy)
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
                self.logger.info(f"got gas price of tx: {gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Tend {strategy_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                    url=self.discord_url,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type=f"Tend {strategy_name}",
                    tx_hash=tx_hash,
                    chain=self.chain,
                    url=self.discord_url,
                )
        except Exception as e:
            self.logger.error(f"Error processing tend tx: {e}")
            send_error_to_discord(
                strategy_name,
                "Tend",
                error=e,
                chain=self.chain,
                keeper_address=self.keeper_address,
            )

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
                        strategy_name,
                        "Harvest",
                        tx_hash=tx_hash,
                        message=msg,
                        chain=self.chain,
                        keeper_address=self.keeper_address,
                    )
        except Exception as e:
            self.logger.error(f"Error processing harvest tx: {e}")
            send_error_to_discord(
                strategy_name,
                "Harvest",
                error=e,
                chain=self.chain,
                keeper_address=self.keeper_address,
            )

    def __process_harvest_mta(
        self,
        voter_proxy: contract,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            voter_proxy (contract): Mstable voter proxy contract
        """
        try:
            tx_hash = self.__send_harvest_mta_tx(voter_proxy)
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                # If successful, update last harvest harvest time
                self.update_last_harvest_time(voter_proxy.address)
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
                self.logger.info(f"got gas price of tx: {gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Harvest MTA",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                    url=self.discord_url,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type=f"Harvest MTA",
                    tx_hash=tx_hash,
                    chain=self.chain,
                    url=self.discord_url,
                )
        except Exception as e:
            self.logger.error(f"Error processing harvestMta tx: {e}")
            send_error_to_discord(
                "",
                "Harvest MTA",
                error=e,
                chain=self.chain,
                keeper_address=self.keeper_address,
            )

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
            tx_hash = get_hash_from_failed_tx_error(
                e, "Harvest", chain=self.chain, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash, max_target_block

    def __send_tend_tx(self, strategy: contract) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            strategy (contract)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        tx_hash = HexBytes(0)
        try:
            tx = self.__build_transaction(strategy.address, function="tend")
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = signed_tx.hash

            self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending tend tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, "Tend", chain=self.chain, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash

    def __send_harvest_mta_tx(self, voter_proxy: contract) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            voter_proxy (contract)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        tx_hash = HexBytes(0)
        try:
            tx = self.__build_transaction(voter_proxy.address, function="harvestMta")
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = signed_tx.hash

            self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending harvestMta tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, "Harvest MTA", chain=self.chain, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash

    def __build_transaction(
        self, address: str, returns: bool = True, function: str = "harvest"
    ) -> dict:
        """Builds transaction depending on which chain we're harvesting. EIP-1559
        requires different handling for ETH txs than the other EVM chains.

        Args:
            contract (contract): contract to use to build harvest tx

        Returns:
            dict: tx dictionary
        """
        options = {
            "nonce": self.web3.eth.get_transaction_count(
                self.keeper_address, "pending"
            ),
            "from": self.keeper_address,
            "gas": GAS_LIMITS[self.chain],
        }
        if self.chain == Network.Ethereum:
            options["maxPriorityFeePerGas"] = get_priority_fee(self.web3)
            options["maxFeePerGas"] = self.__get_effective_gas_price()
        else:
            options["gasPrice"] = self.__get_effective_gas_price()

        if function == "harvest":
            self.logger.info(
                f"estimated gas fee: {self.__estimate_harvest_gas(address, returns)}"
            )
            return self.__build_harvest_transaction(address, returns, options)
        elif function == "tend":
            self.logger.info(f"estimated gas fee: {self.__estimate_tend_gas(address)}")
            return self.__build_tend_transaction(address, options)
        elif function == "harvestMta":
            self.logger.info(
                f"estimated gas fee: {self.__estimate_harvest_mta_gas(address)}"
            )
            return self.__build_harvest_mta_transaction(address, options)

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

    def __build_tend_transaction(self, strategy_address: str, options: dict) -> dict:
        return self.keeper_acl.functions.tend(strategy_address).buildTransaction(
            options
        )

    def __build_harvest_mta_transaction(
        self, voter_proxy_address: str, options: dict
    ) -> dict:
        return self.keeper_acl.functions.harvestMta(
            voter_proxy_address
        ).buildTransaction(options)

    def estimate_gas_fee(
        self, address: str, returns: bool = True, function: str = "harvest"
    ) -> Decimal:
        current_gas_price = self.__get_effective_gas_price()
        if function == "harvest":
            estimated_gas = self.__estimate_harvest_gas(address, returns)
        elif function == "tend":
            estimated_gas = self.__estimate_tend_gas(address)
        elif function == "harvestMta":
            estimated_gas = self.__estimate_harvest_mta_gas(address)

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

    def __estimate_harvest_mta_gas(self, voter_proxy_address: str) -> Decimal:
        return Decimal(
            self.keeper_acl.functions.harvestMta(voter_proxy_address).estimateGas(
                {"from": self.keeper_address}
            )
        )

    def __get_effective_gas_price(self) -> int:
        if self.chain == Network.Polygon:
            response = requests.get("https://gasstation-mainnet.matic.network").json()
            gas_price = self.web3.toWei(int(response.get("fast") * 1.1), "gwei")
        elif self.chain == Network.Arbitrum:
            gas_price = int(1.1 * self.web3.eth.gas_price)
            # Estimated gas price + buffer
        elif self.chain == Network.Ethereum:
            # EIP-1559
            gas_price = get_effective_gas_price(self.web3)
        return gas_price

    def update_last_harvest_time(self, strategy_address: str):
        self.last_harvest_times[strategy_address] = self.web3.eth.get_block("latest")[
            "timestamp"
        ]
