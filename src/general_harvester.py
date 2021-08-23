import logging
import os
import requests
import sys
from decimal import Decimal
from hexbytes import HexBytes
from time import sleep
from web3 import Web3, contract, exceptions

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))

from harvester import IHarvester
from utils import (
    confirm_transaction,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
    get_hash_from_failed_tx_error,
    get_latest_base_fee,
)

logging.basicConfig(level=logging.INFO)

HARVEST_THRESHOLD = 0.0005  # min ratio of want to total vault AUM required to harvest

GAS_LIMIT = 6000000
MAX_GAS_PRICE = int(60e9)  # 200 gwei
PRIORITY_FEE_MULTIPLIER = 5  # Pay 5x the average priority fee
# PRIORITY_FEE = int(20e9)  # 20 gwei
NUM_FLASHBOTS_BUNDLES = 6


class GeneralHarvester(IHarvester):
    def __init__(
        self,
        chain: str = "eth",
        web3: Web3 = None,
        keeper_acl: str = os.getenv("KEEPER_ACL"),
        keeper_address: str = os.getenv("KEEPER_ADDRESS"),
        keeper_key: str = os.getenv("KEEPER_KEY"),
        base_oracle_address: str = os.getenv("ETH_USD_CHAINLINK"),
        use_flashbots=False,
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

        self.use_flashbots = use_flashbots

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
        if not self.__is_keeper_whitelisted(strategy, "harvest"):
            raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

        want_address = strategy.functions.want().call()
        want = self.web3.eth.contract(
            address=want_address,
            abi=get_abi(self.chain, "erc20"),
        )
        vault_balance = want.functions.balanceOf(strategy.address).call()
        self.logger.info(f"vault balance: {vault_balance}")

        want_to_harvest = (
            self.estimate_harvest_amount(strategy.address, want)
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
                harvested=want_to_harvest,
            )

    def harvest_no_return(
        self,
        strategy: contract,
    ):
        strategy_name = strategy.functions.getName().call()
        # TODO: update for ACL
        if not self.__is_keeper_whitelisted(strategy, "harvest"):
            raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

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

    def tend(self, strategy: contract):
        strategy_name = strategy.functions.getName().call()
        # TODO: update for ACL
        if not self.__is_keeper_whitelisted(strategy, "tend"):
            raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

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

    def estimate_harvest_amount(self, strategy: contract, want: contract) -> Decimal:
        want_decs = want.functions.decimals().call()
        want_post_harvest = (
            self.keeper_acl.functions.harvest(strategy.address).call(
                {"from": self.keeper_address}
            )
        )
        want_pre_harvest = strategy.functions.balanceOf().call()
        self.logger.info(f"pre harvest want: {want_pre_harvest}")
        self.logger.info(f"post harvest want: {want_post_harvest}")
        est_want_change = want_post_harvest - want_pre_harvest
        # call badger api to get prices
        prices = requests.get("https://api.badger.finance/v2/prices?currency=eth").json()
        price_per_want = prices.get(want.address)
        return price_per_want * est_want_change

    def is_profitable(self) -> bool:
        # TODO: Implement this

        # harvest if ideal want change is > 0.05% of total vault assets
        # should_harvest = want_to_harvest / vault_balance >= HARVEST_THRESHOLD
        return True

    def __is_keeper_whitelisted(self, strategy: contract, function: str) -> bool:
        """Checks if the bot we're using is whitelisted for the strategy.

        Args:
            strategy (contract)

        Returns:
            bool: True if our bot is whitelisted to make function calls to strategy,
            False otherwise.
        """
        if function == "harvest":
            key = self.keeper_acl.functions.HARVESTER_ROLE().call()
        elif function == "tend":
            key = self.keeper_acl.functions.TENDER_ROLE().call()
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
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                self.logger.info(f"got gas price of tx: {gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Tend {strategy_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type=f"Tend {strategy_name}",
                    tx_hash=tx_hash,
                    chain=self.chain,
                )
        except Exception as e:
            self.logger.error(f"Error processing tend tx: {e}")
            send_error_to_discord(strategy_name, "Tend", error=e)

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
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                self.logger.info(f"got gas price of tx: {gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Harvest {strategy_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                )
            elif tx_hash != HexBytes(0):
                if not self.use_flashbots:
                    send_success_to_discord(
                        tx_type=f"Harvest {strategy_name}",
                        tx_hash=tx_hash,
                        chain=self.chain,
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
        try:
            tx = self.__build_transaction(strategy.address, function="tend")
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = signed_tx.hash

            self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending tend tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(e, "Tend")
        finally:
            return tx_hash

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
        }
        if self.chain == "eth":
            # Use x times recommended priority fee as miner tip
            self.logger.info(f"max_priority_fee: {self.web3.eth.max_priority_fee}")
            priority_fee = PRIORITY_FEE_MULTIPLIER * self.web3.eth.max_priority_fee
            # priority_fee = PRIORITY_FEE
            options["maxPriorityFeePerGas"] = priority_fee
            # Hard limit on the gas price
            options["maxFeePerGas"] = MAX_GAS_PRICE
            options["gas"] = GAS_LIMIT
        else:
            options["gasPrice"] = self.__get_effective_gas_price()

        if function == "harvest":
            self.logger.info(
                f"estimated gas fee: {self.__estimate_harvest_gas(strategy_address, returns)}"
            )
            return self.__build_harvest_transaction(strategy_address, returns, options)
        elif function == "tend":
            self.logger.info(
                f"estimated gas fee: {self.__estimate_tend_gas(strategy_address)}"
            )
            return self.__build_tend_transaction(strategy_address, options)

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
        elif self.chain == "eth":
            # TODO: Currently using max fee (per gas) that can be used for this tx. Maybe use base + priority (for average).
            base_fee = get_latest_base_fee(self.web3)
            # Use x times the recommended priority fee as miner tip
            priority_fee = PRIORITY_FEE_MULTIPLIER * self.web3.eth.max_priority_fee
            gas_price = 2 * base_fee + priority_fee
        return gas_price

    def __get_gas_price_of_tx(self, tx_hash: HexBytes) -> Decimal:
        """Gets the actual amount of gas used by the transaction and converts
        it from gwei to USD value for monitoring.

        Args:
            tx_hash (HexBytes): tx id of target transaction

        Returns:
            Decimal: USD value of gas used in tx
        """
        try:
            tx_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
        except exceptions.TransactionNotFound:
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

        total_gas_used = Decimal(tx_receipt.get("gasUsed", 0))
        self.logger.info(f"gas used: {total_gas_used}")
        if self.chain == "eth":
            gas_price_base = Decimal(tx_receipt.get("effectiveGasPrice", 0) / 10 ** 18)
        else:
            tx = self.web3.eth.get_transaction(tx_hash)
            gas_price_base = Decimal(tx.get("gasPrice", 0) / 10 ** 18)

        base_usd = Decimal(
            self.base_usd_oracle.functions.latestAnswer().call()
            / 10 ** self.base_usd_oracle.functions.decimals().call()
        )

        return total_gas_used * gas_price_base * base_usd
