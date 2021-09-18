from decimal import Decimal
from hexbytes import HexBytes
import json
import logging
import os
import requests
import sys
from time import sleep
from web3 import Web3, contract, exceptions

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./")))

from utils import (
    confirm_transaction,
    send_error_to_discord,
    send_success_to_discord,
    get_abi,
    get_hash_from_failed_tx_error,
)
from tx_utils import get_priority_fee, get_effective_gas_price, get_gas_price_of_tx
from constants import EARN_OVERRIDE_THRESHOLD, EARN_PCT_THRESHOLD

logging.basicConfig(level=logging.INFO)

GAS_LIMIT = int(1e6)
EARN_EXCEPTIONS = {}


class Earner:
    def __init__(
        self,
        chain: str = "eth",
        keeper_acl: str = os.getenv("KEEPER_ACL"),
        keeper_address: str = os.getenv("KEEPER_ADDRESS"),
        keeper_key: str = os.getenv("KEEPER_KEY"),
        base_oracle_address: str = os.getenv("ETH_USD_CHAINLINK"),
        web3: Web3 = None,
        discord_url: str = None,
    ):
        self.logger = logging.getLogger("earner")
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
        self.discord_url = discord_url

    def earn(self, vault: contract, strategy: contract, sett_name: str = None):
        override_threshold = EARN_EXCEPTIONS.get(
            strategy.address, self.web3.toWei(EARN_OVERRIDE_THRESHOLD, "ether")
        )

        # handle skipping outside of earn call, only call this on setts we want to earn
        controller = self.web3.eth.contract(
            address=vault.functions.controller().call(),
            abi=get_abi(self.chain, "controller"),
        )
        want = self.web3.eth.contract(
            address=vault.functions.token().call(), abi=get_abi(self.chain, "erc20")
        )

        # Pre safety checks
        swant_address = strategy.functions.want().call()
        self.logger.info(f"{want.address} == {swant_address}")
        assert want.address == swant_address
        assert strategy.functions.controller().call() == controller.address
        assert vault.functions.controller().call() == controller.address
        assert controller.functions.strategies(want.address).call() == strategy.address

        vault_before = want.functions.balanceOf(vault.address).call()
        strategy_before = strategy.functions.balanceOf().call()

        if self.should_earn(override_threshold, vault_before, strategy_before):
            self.__process_earn(vault, sett_name)

    def should_earn(
        self, override_threshold: int, vault_balance: int, strategy_balance: int
    ) -> bool:
        # Always allow earn on first run
        if strategy_balance == 0:
            self.logger.info("No strategy balance, earn")
            return True
        # Earn if deposits have accumulated over a static threshold
        if vault_balance >= override_threshold:
            self.logger.info(
                f"Vault balance of {vault_balance} over earn threshold override of {override_threshold}"
            )
            return True
        # Earn if deposits have accumulated over % threshold
        if vault_balance / strategy_balance > EARN_PCT_THRESHOLD:
            self.logger.info(
                f"Vault balance of {vault_balance} and strategy balance of {strategy_balance} over standard % threshold of {EARN_PCT_THRESHOLD}"
            )

            return True
        else:
            self.logger.info(
                {
                    "vault_balance": vault_balance,
                    "strategy_balance": strategy_balance,
                    "override_threshold": override_threshold,
                    "vault_to_strategy_ratio": vault_balance / strategy_balance,
                }
            )
            return False

    def __is_keeper_whitelisted(self, strategy: contract) -> bool:
        """Checks if the bot we're using is whitelisted for the strategy.

        Args:
            strategy (contract)

        Returns:
            bool: True if our bot is whitelisted to make function calls to strategy,
            False otherwise.
        """
        earner_key = self.keeper_acl.functions.EARNER_ROLE().call()
        return self.keeper_acl.functions.hasRole(earner_key, self.keeper_address).call()

    def __process_earn(
        self,
        vault: contract = None,
        sett_name: str = None,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            vault (contract, optional): Defaults to None.
            sett_name (str, optional): Defaults to None.
            overrides (dict, optional): Dictionary settings for transaction. Defaults to None.
        """
        try:
            tx_hash = self.__send_earn_tx(vault)
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
                self.logger.info(f"got gas price of tx: ${gas_price_of_tx}")
                send_success_to_discord(
                    tx_type=f"Earn {sett_name}",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                    url=self.discord_url,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type=f"Earn {sett_name}",
                    tx_hash=tx_hash,
                    chain=self.chain,
                    url=self.discord_url,
                )
        except Exception as e:
            self.logger.error(f"Error processing earn tx: {e}")
            send_error_to_discord(sett_name, "Earn", error=e)

    def __send_earn_tx(self, vault: contract) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            vault (contract)
            overrides (dict)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            tx = self.__build_transaction(vault.address)
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = signed_tx.hash
            self.logger.info(f"attempted tx_hash: {tx_hash}")
            self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except ValueError as e:
            self.logger.error(f"Error in sending earn tx: {e}")
            tx_hash = get_hash_from_failed_tx_error(e, "Earn")
        finally:
            return tx_hash

    def __get_gas_price(self) -> int:
        if self.chain == "poly":
            response = requests.get("https://gasstation-mainnet.matic.network").json()
            gas_price = self.web3.toWei(int(response.get("fast") * 1.1), "gwei")
        elif self.chain == "eth":
            gas_price = get_effective_gas_price(self.web3)
        elif self.chain == "arbitrum":
            gas_price = int(1.1 * self.web3.eth.gas_price)

        return gas_price

    def __build_transaction(self, strategy_address: str) -> dict:
        """Builds transaction depending on which chain we're earning. EIP-1559
        requires different handling for ETH txs than the other EVM chains.

        Args:
            contract (contract): contract to use to build earn tx

        Returns:
            dict: tx dictionary
        """
        options = {
            "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
            "from": self.keeper_address,
            "gas": GAS_LIMIT,
        }
        if self.chain == "eth":
            options["maxPriorityFeePerGas"] = get_priority_fee(self.web3)
            options["maxFeePerGas"] = self.__get_gas_price()
        else:
            options["gasPrice"] = self.__get_gas_price()
        return self.keeper_acl.functions.earn(strategy_address).buildTransaction(
            options
        )
