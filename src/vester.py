import logging
import os
import requests

from hexbytes import HexBytes
from web3 import Web3

from config.constants import ARB_BADGER
from config.constants import ARB_VESTER
from config.constants import GAS_LIMITS
from config.enums import Network
from src.tx_utils import get_effective_gas_price
from src.tx_utils import get_gas_price_of_tx
from src.tx_utils import get_priority_fee
from src.web3_utils import confirm_transaction
from src.discord_utils import get_hash_from_failed_tx_error
from src.discord_utils import send_success_to_discord
from src.discord_utils import send_error_to_discord
from src.utils import get_abi

MAX_GAS_PRICE = int(1000e9)  # 1000 gwei
CHAIN_CURRENCY = {Network.Arbitrum: ARB_BADGER}


class Vester:
    def __init__(
        self,
        chain: Network,
        discord_url: str,
        keeper_address=os.getenv("KEEPER_ADDRESS"),
        keeper_key=os.getenv("KEEPER_KEY"),
        base_oracle_address: str = os.getenv("ETH_USD_CHAINLINK"),
        vesting_contract_address: str = ARB_VESTER,
        web3=os.getenv("ETH_NODE_URL"),
    ):
        self.logger = logging.getLogger(__name__)
        self.web3 = Web3(Web3.HTTPProvider(web3))  # get secret here
        self.chain = chain
        self.keeper_key = keeper_key  # get secret here
        self.keeper_address = keeper_address  # get secret here
        self.eth_usd_oracle = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(base_oracle_address),
            abi=get_abi(self.chain, "oracle"),
        )
        self.vesting_contract = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(vesting_contract_address),
            abi=get_abi(self.chain, "vester"),
        )
        self.discord_url = discord_url

    def vest(self):
        self._process_vest_release()

    def _process_vest_release(self):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring
        """
        try:
            tx_hash = self._send_vest_tx()
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.eth_usd_oracle, tx_hash, Network.Ethereum
                )
                send_success_to_discord(
                    tx_type="Release Vested Badger to Tree",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                    url=self.discord_url,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type="Release Vested Badger to Tree",
                    tx_hash=tx_hash,
                    chain=self.chain,
                    url=self.discord_url,
                )
        except Exception as e:
            self.logger.error(f"Error processing release tx: {e}")
            send_error_to_discord(
                "Badger",
                "Vest",
                error=e,
                chain=self.chain,
                keeper_address=self.keeper_address,
            )

    def _send_vest_tx(self) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        tx_hash = HexBytes(0)
        try:
            options = {
                "nonce": self.web3.eth.get_transaction_count(
                    self.keeper_address, "pending"
                ),
                "from": self.keeper_address,
                "gas": GAS_LIMITS[self.chain],
            }
            if self.chain == Network.Ethereum:
                options["maxPriorityFeePerGas"] = get_priority_fee(self.web3)
                options["maxFeePerGas"] = self._get_effective_gas_price()
            else:
                options["gasPrice"] = self._get_effective_gas_price()
                self.logger.info(f"max_priority_fee: {self.web3.eth.max_priority_fee}")

            tx = self.vesting_contract.functions.release(
                CHAIN_CURRENCY[self.chain]
            ).buildTransaction(options)
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending vesting release tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(
                e, self.logger, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash

    def _get_effective_gas_price(self):
        if self.chain == Network.Polygon:
            response = requests.get("https://gasstation-mainnet.matic.network").json()
            gas_price = self.web3.toWei(int(response.get("fast") * 1.1), "gwei")
        elif self.chain in [Network.Arbitrum, Network.Fantom]:
            gas_price = int(1.1 * self.web3.eth.gas_price)
            # Estimated gas price + buffer
        elif self.chain == Network.Ethereum:
            # EIP-1559
            gas_price = get_effective_gas_price(self.web3)
        return gas_price
