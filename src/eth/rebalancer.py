import logging
import os
import sys

from decimal import Decimal
from hexbytes import HexBytes
from time import sleep
from web3 import Web3, contract, exceptions


from config.enums import Network
from src.utils import (
    confirm_transaction,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
)
from src.tx_utils import (
    get_gas_price_of_tx,
    get_effective_gas_price,
    get_priority_fee,
)

logging.basicConfig(level=logging.INFO)

GAS_LIMIT = 1000000
MAX_GAS_PRICE = int(200e9)  # 200 gwei
DIGG_TOKEN = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
NUM_FLASHBOTS_BUNDLES = 6


class Rebalancer:
    def __init__(
        self,
        chain: str = Network.Ethereum,
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
        key = self.keeper_acl.functions.HARVESTER_ROLE().call()
        return self.keeper_acl.functions.hasRole(key, self.keeper_address).call()

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
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
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
        tx_hash = HexBytes(0)
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
        priority_fee = get_priority_fee(self.web3)
        self.logger.info(f"max_priority_fee: {priority_fee}")
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
            "maxPriorityFeePerGas": priority_fee,
            "maxFeePerGas": MAX_GAS_PRICE,
            "gas": GAS_LIMIT,
        }
        tx = self.keeper_acl.functions.rebalance(strategy.address).buildTransaction(
            options
        )

        return tx

    def estimate_gas_fee(self, strategy: contract) -> Decimal:
        current_gas_price = get_effective_gas_price(self.web3)
        estimated_gas = self.keeper_acl.functions.rebalance(
            strategy.address
        ).estimateGas({"from": self.keeper_address})
        self.logger.info(f"estimated gas fee: {estimated_gas}")

        return Decimal(current_gas_price * estimated_gas)
