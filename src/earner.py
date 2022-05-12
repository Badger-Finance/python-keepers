import logging
import os
import traceback
from typing import Optional
from typing import Tuple

import requests
from hexbytes import HexBytes
from web3 import Web3
from web3 import contract

from config.constants import BASE_CURRENCIES
from config.constants import CRITICAL_VAULTS
from config.constants import EARN_OVERRIDE_THRESHOLD
from config.constants import EARN_PCT_THRESHOLD
from config.constants import ETH_BVECVX_STRATEGY
from config.constants import FTM_BVEOXD_VOTER
from config.constants import FTM_OXD_BVEOXD_VAULT
from config.enums import Network
from src.discord_utils import send_critical_error_to_discord
from src.token_utils import get_token_price
from src.tx_utils import get_effective_gas_price
from src.tx_utils import get_gas_price_of_tx
from src.tx_utils import get_tx_options
from src.tx_utils import sign_and_send_tx
from src.utils import get_abi
from src.discord_utils import get_hash_from_failed_tx_error
from src.discord_utils import send_error_to_discord
from src.discord_utils import send_success_to_discord
from src.web3_utils import confirm_transaction

logging.basicConfig(level=logging.INFO)

GAS_LIMITS = {
    Network.Ethereum: 1_500_000,
    Network.Polygon: 1_000_000,
    Network.Arbitrum: 3_000_000,
    Network.Fantom: 6_000_000,
}
EARN_EXCEPTIONS = {ETH_BVECVX_STRATEGY: 20}


class Earner:
    def __init__(
        self,
        chain: str = Network.Ethereum,
        keeper_acl: str = os.getenv("KEEPER_ACL"),
        keeper_address: str = os.getenv("KEEPER_ADDRESS"),
        keeper_key: str = os.getenv("KEEPER_KEY"),
        base_oracle_address: str = os.getenv("ETH_USD_CHAINLINK"),
        web3: Web3 = None,
        discord_url: str = None,
    ):
        self.logger = logging.getLogger(__name__)
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
            strategy.address, EARN_OVERRIDE_THRESHOLD
        )

        want = self.web3.eth.contract(
            address=vault.functions.token().call(), abi=get_abi(self.chain, "erc20")
        )

        # Pre safety checks
        swant_address = strategy.functions.want().call()
        self.logger.info(f"{want.address} == {swant_address}")
        assert want.address == swant_address

        vault_balance, strategy_balance = self.get_balances(vault, strategy, want)

        if self.should_earn(override_threshold, vault_balance, strategy_balance):
            self.__process_earn(vault, sett_name)
            if vault.address == FTM_OXD_BVEOXD_VAULT:
                self.bveoxd_vote()

    def get_balances(
        self, vault: contract, strategy: contract, want: contract
    ) -> Tuple[float, float]:
        """Returns the balance of want in the vault and strategy.

        Args:
            vault (contract): vault web3 contract object
            strategy (contract): strategy web3 contract object
            want (contract): want web3 contract object

        Returns:
            Tuple[float, float]: want in vault denominated in selected currenct, want in strat
                denominated in selected currency.
        """
        currency = BASE_CURRENCIES[self.chain]
        if self.chain == Network.Fantom:
            price_per_want = get_token_price(
                want.address, currency, self.chain, use_staging=True
            )
        else:
            price_per_want = get_token_price(want.address, currency, self.chain)

        self.logger.info(f"price per want: {price_per_want} {currency}")

        want_decimals = want.functions.decimals().call()

        vault_balance = want.functions.balanceOf(vault.address).call()
        strategy_balance = strategy.functions.balanceOf().call()

        vault_balance = price_per_want * vault_balance / 10 ** want_decimals
        strategy_balance = price_per_want * strategy_balance / 10 ** want_decimals

        return vault_balance, strategy_balance

    def should_earn(
        self, override_threshold: int, vault_balance: int, strategy_balance: int
    ) -> bool:
        # Always allow earn on first run
        self.logger.info(
            {"strategy_balance": strategy_balance, "vault_balance": vault_balance}
        )
        if strategy_balance == 0:
            if vault_balance == 0:
                self.logger.info("No strategy balance or vault balance")
                return False
            else:
                self.logger.info("No strategy balance, earn")
                return True
        # Earn if deposits have accumulated over a static threshold
        if vault_balance >= override_threshold:
            self.logger.info(
                f"Vault balance of {vault_balance} "
                f"over earn threshold override of {override_threshold}"
            )
            return True
        # Earn if deposits have accumulated over % threshold
        if vault_balance / strategy_balance > EARN_PCT_THRESHOLD:
            self.logger.info(
                f"Vault balance of {vault_balance} and strategy balance "
                f"of {strategy_balance} over standard % threshold of {EARN_PCT_THRESHOLD}"
            )

            return True
        else:
            self.logger.info(
                {
                    "vault_balance": vault_balance,
                    "strategy_balance": strategy_balance,
                    "override_threshold": override_threshold,
                    "vault_to_strategy_ratio": vault_balance / strategy_balance
                    if strategy_balance > 0
                    else 0,
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
            if vault and vault.address in CRITICAL_VAULTS:
                send_critical_error_to_discord(sett_name, "Earn", chain=self.chain)
            else:
                send_error_to_discord(
                    sett_name,
                    "Earn",
                    error=e,
                    chain=self.chain,
                    keeper_address=self.keeper_address,
                )

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
            self.logger.error(f"Error in sending earn tx: {traceback.format_exc()}")
            tx_hash = get_hash_from_failed_tx_error(
                e, "Earn", chain=self.chain, keeper_address=self.keeper_address
            )
        finally:
            return tx_hash

    def __get_gas_price(self) -> int:
        if self.chain == Network.Polygon:
            response = requests.get("https://gasstation-mainnet.matic.network").json()
            gas_price = self.web3.toWei(int(response.get("fast") * 1.1), "gwei")
        elif self.chain == Network.Ethereum:
            gas_price = get_effective_gas_price(self.web3)
        elif self.chain in [Network.Arbitrum, Network.Fantom]:
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
        options = get_tx_options(self.web3, self.chain, self.keeper_address)
        return self.keeper_acl.functions.earn(strategy_address).buildTransaction(
            options
        )

    def bveoxd_vote(
        self,
    ) -> None:
        voter = self.web3.eth.contract(
            address=FTM_BVEOXD_VOTER, abi=get_abi(Network.Fantom, "bveoxd_voter")
        )

        try:
            options = get_tx_options(self.web3, self.chain, self.keeper_address)
            tx = voter.functions.vote().buildTransaction(options)
            tx_hash = sign_and_send_tx(self.web3, tx, self.keeper_key)
        except Exception:
            self.logger.error(f"Error in sending vote tx: {traceback.format_exc()}")
            tx_hash = HexBytes(0)

        try:
            succeeded, _ = confirm_transaction(self.web3, tx_hash)
            if succeeded:
                gas_price_of_tx = get_gas_price_of_tx(
                    self.web3, self.base_usd_oracle, tx_hash, self.chain
                )
                self.logger.info(f"got gas price of tx: ${gas_price_of_tx}")
                send_success_to_discord(
                    tx_type="Vote bveOXD",
                    tx_hash=tx_hash,
                    gas_cost=gas_price_of_tx,
                    chain=self.chain,
                    url=self.discord_url,
                )
            elif tx_hash != HexBytes(0):
                send_success_to_discord(
                    tx_type="Vote bveOXD",
                    tx_hash=tx_hash,
                    chain=self.chain,
                    url=self.discord_url,
                )
        except Exception as e:
            self.logger.error(f"Error processing earn tx: {e}")
            send_error_to_discord(
                "bveOXD",
                "Vote bveOXD",
                error=e,
                chain=self.chain,
                keeper_address=self.keeper_address,
            )
