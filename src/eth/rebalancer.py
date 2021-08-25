import logging
import os
import requests
import sys
from decimal import Decimal
from hexbytes import HexBytes
from time import sleep
from web3 import Web3, contract, exceptions

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from utils import (
    confirm_transaction,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
    get_hash_from_failed_tx_error,
    get_latest_base_fee,
)

logging.basicConfig(level=logging.INFO)

GAS_LIMIT = 1000000
MAX_GAS_PRICE = int(200e9)  # 200 gwei
STABILIZE_STRAT = "0xA6af1B913E205B8E9B95D3B30768c0989e942316"
DIGG_TOKEN = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
NUM_FLASHBOTS_BUNDLES = 6


class Rebalancer:
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
        self.logger = logging.getLogger("rebalancer")
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
        self.digg = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(DIGG_TOKEN),
            abi=get_abi(self.chain, "erc20"),
        )

        self.use_flashbots = use_flashbots

    def rebalance(
        self,
        strategy: contract,
    ):
        """Orchestration function that rebalances digg stablilizer sett.

        Args:
            strategy (contract)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        strategy_name = strategy.functions.getName().call()
        # TODO: rn using keeper address bc acl not set up for diff funcs
        if not self.__is_keeper_whitelisted(strategy):
            raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

        digg_current_supply = self.digg.functions.totalSupply().call()
        self.logger.info(f"current digg supply: {digg_current_supply}")
        digg_last_supply = strategy.functions.lastDiggTotalSupply().call()
        self.logger.info(f"last digg supply: {digg_last_supply}")

        if digg_current_supply != digg_last_supply:
            last_digg_price = strategy.functions.lastDiggPrice().call() / 10 ** 18
            self.logger.info(f"last digg price: {last_digg_price}")
            amt_to_trade = strategy.functions.tradeAmountLeft().call()
            self.logger.info(f"amt left to trade: {amt_to_trade}")

            gas_fee = self.estimate_gas_fee(strategy)
            self.logger.info(f"estimated gas cost: {gas_fee}")

            self.__process_rebalance(
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
        return strategy.functions.keeper().call() == self.keeper_address

    def __process_rebalance(
        self,
        strategy: contract = None,
        strategy_name: str = None,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            strategy (contract, optional): Defaults to None.
            strategy_name (str, optional): Defaults to None.
        """
        try:
            tx_hash, max_target_block = self.__send_rebalance_tx(strategy)
            succeeded, msg = confirm_transaction(
                self.web3, tx_hash, max_block=max_target_block
            )
            if succeeded:
                gas_price_of_tx = self.__get_gas_price_of_tx(tx_hash)
                self.logger.info(f"got gas price of tx: {gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Rebalance {strategy_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                )
            elif tx_hash != HexBytes(0):
                if not self.use_flashbots:
                    send_success_to_discord(
                        tx_type=f"Rebalance {strategy_name}",
                        tx_hash=tx_hash,
                        chain=self.chain,
                    )
                else:
                    send_error_to_discord(
                        strategy_name, "Rebalance", tx_hash=tx_hash, message=msg
                    )
        except Exception as e:
            self.logger.error(f"Error processing rebalance tx: {e}")
            send_error_to_discord(strategy_name, "Rebalance", error=e)

    def __send_rebalance_tx(self, strategy: contract) -> HexBytes:
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
        tx_hash = None
        try:
            tx = self.__build_transaction(strategy)
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
            self.logger.error(f"Error in sending rebalance tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(e, "Rebalance")
        finally:
            return tx_hash, max_target_block

    def __build_transaction(self, strategy: contract) -> dict:
        """Builds transaction depending on which chain we're rebalancing. EIP-1559
        requires different handling for ETH txs than the other EVM chains.

        Args:
            contract (contract): contract to use to build rebalance tx

        Returns:
            dict: tx dictionary
        """
        # Use x times recommended priority fee as miner tip
        gas_data = self.web3.eth.fee_history("0x4", "latest", [70])
        rewards = gas_data.get("reward", [[int(10e9)]])
        priority_fee = int(sum([r[0] for r in rewards]) / len(rewards))
        self.logger.info(f"max_priority_fee: {priority_fee}")
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
            "maxPriorityFeePerGas": priority_fee,
            "maxFeePerGas": MAX_GAS_PRICE,
            "gas": GAS_LIMIT,
        }
        tx = strategy.functions.rebalance().buildTransaction(options)

        return tx

    def estimate_gas_fee(self, strategy: contract) -> Decimal:
        current_gas_price = self.__get_effective_gas_price()
        estimated_gas = strategy.functions.rebalance().estimateGas(
            {"from": self.keeper_address}
        )
        self.logger.info(f"estimated gas fee: {estimated_gas}")

        return Decimal(current_gas_price * estimated_gas)

    def __get_effective_gas_price(self) -> int:
        # TODO: Currently using max fee (per gas) that can be used for this tx. Maybe use base + priority (for average).
        base_fee = get_latest_base_fee(self.web3)
        # Use x times the recommended priority fee as miner tip
        gas_data = self.web3.eth.fee_history("0x4", "latest", [70])
        rewards = gas_data.get("reward", [[int(10e9)]])
        priority_fee = sum([r[0] for r in rewards]) / len(rewards)
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
