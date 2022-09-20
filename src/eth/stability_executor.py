import os
from decimal import Decimal

from hexbytes import HexBytes
from web3 import Web3
from web3 import contract

from config.enums import Network
from src.discord_utils import send_error_to_discord
from src.discord_utils import send_success_to_discord
from src.json_logger import logger
from src.tx_utils import get_effective_gas_price
from src.tx_utils import get_gas_price_of_tx
from src.tx_utils import get_priority_fee
from src.utils import get_abi
from src.web3_utils import confirm_transaction

GAS_LIMIT = 1000000
MAX_GAS_PRICE = int(200e9)  # 200 gwei
NUM_FLASHBOTS_BUNDLES = 6


class StabilityExecutor:
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

    def execute_batch(
        self,
        strategy: contract,
    ):
        """Orchestration function that executes batch of trades if still some left.

        Args:
            strategy (contract)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        strategy_name = strategy.functions.getName().call()
        # TODO: rn using keeper address bc acl not set up for diff funcs
        if not self.__is_keeper_whitelisted(strategy):
            raise ValueError(f"Keeper is not whitelisted for {strategy_name}")

        amt_to_trade = strategy.functions.tradeAmountLeft().call()
        logger.info(f"amt left to trade: {amt_to_trade}")

        if amt_to_trade > 0:

            gas_fee = self.estimate_gas_fee(strategy)
            logger.info(f"estimated gas cost: {gas_fee}")

            self.__process_batch_execute(
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

    def __process_batch_execute(
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
            tx_hash, max_target_block = self.__send_batch_execute_tx(strategy)
            succeeded, msg = confirm_transaction(
                self.web3, tx_hash, max_block=max_target_block
            )
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
                send_success_to_discord(
                    tx_type=f"Execute Trade Batch {strategy_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                )
            elif tx_hash != HexBytes(0):
                if not self.use_flashbots:
                    send_success_to_discord(
                        tx_type=f"Execute Trade Batch {strategy_name}",
                        tx_hash=tx_hash,
                        chain=self.chain,
                    )
                else:
                    send_error_to_discord(
                        strategy_name,
                        "Execute Trade Batch",
                        tx_hash=tx_hash,
                        message=msg,
                    )
        except Exception as e:
            logger.error(f"Error processing execute trade batch tx: {e}")
            send_error_to_discord(strategy_name, "Execute Trade Batch", error=e)

    def __send_batch_execute_tx(self, strategy: contract) -> HexBytes:
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
                logger.info(f"Bundle broadcasted at {max_target_block}")

        except ValueError as e:
            logger.error(f"Error in sending execute trade batch tx: {e}")
        finally:
            return tx_hash, max_target_block

    def __build_transaction(self, strategy: contract) -> dict:
        """Builds transaction for the executeTradeBatch function.

        Args:
            contract (contract): contract to use to build execute trade batch tx

        Returns:
            dict: tx dictionary
        """
        # Use x times recommended priority fee as miner tip
        priority_fee = get_priority_fee(self.web3)
        logger.info(f"max_priority_fee: {priority_fee}")
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
            "maxPriorityFeePerGas": priority_fee,
            "maxFeePerGas": MAX_GAS_PRICE,
            "gas": GAS_LIMIT,
        }
        tx = strategy.functions.executeTradeBatch().buildTransaction(options)

        return tx

    def estimate_gas_fee(self, strategy: contract) -> Decimal:
        current_gas_price = get_effective_gas_price(self.web3)
        estimated_gas = strategy.functions.executeTradeBatch().estimateGas(
            {"from": self.keeper_address}
        )
        logger.info(f"estimated gas fee: {estimated_gas}")

        return Decimal(current_gas_price * estimated_gas)
