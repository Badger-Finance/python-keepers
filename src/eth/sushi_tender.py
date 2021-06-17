from decimal import Decimal
from hexbytes import HexBytes
import os
from src.eth.sushi_harvester import SushiHarvester
import sys
from web3 import contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.utils import send_success_to_discord, send_error_to_discord

CHEF = "0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd"


class SushiTender(SushiHarvester):
    def tend(
        self,
        sett_name: str,
        strategy_address: str,
    ):
        """Orchestration function that tends outstanding Sushi awards.

        Args:
            sett_name (str)
            strategy_address (str)

        Raises:
            ValueError: If the keeper isn't whitelisted, throw an error and alert user.
        """
        strategy = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(strategy_address),
            abi=self._SushiHarvester__get_abi("strategy"),
        )

        if not self._SushiHarvester__is_keeper_whitelisted(strategy):
            raise ValueError(f"Keeper is not whitelisted for {sett_name}")

        pool_id = strategy.functions.pid().call()

        claimable_rewards = self.get_tendable_rewards_amount(
            pool_id=pool_id, strategy_address=strategy_address
        )
        self.logger.info(f"claimable rewards: {claimable_rewards}")

        current_price_eth = self.get_current_rewards_price()
        self.logger.info(f"current rewards price per token (ETH): {current_price_eth}")

        gas_fee = self.estimate_gas_fee(strategy)

        should_tend = self.is_profitable(claimable_rewards, current_price_eth, gas_fee)
        self.logger.info(f"Should we tend: {should_tend}")

        if should_tend:
            eth_usd_price = Decimal(
                self.eth_usd_oracle.functions.latestRoundData().call()[1] / 10 ** 8
            )

            self.__process_tend(
                strategy=strategy,
                sett_name=sett_name,
                overrides={
                    "from": self.keeper_address,
                    "gas_limit": 12000000,
                    "allow_revert": True,
                },
                tended=claimable_rewards * current_price_eth * eth_usd_price,
            )

    def get_tendable_rewards_amount(self, pool_id: int, strategy_address: str):
        chef = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(CHEF),
            abi=self._SushiHarvester__get_abi("chef"),
        )
        claimable_rewards = (
            chef.functions.pendingSushi(pool_id, strategy_address).call()
            / 10 ** self.sushi_decimals
        )
        return Decimal(claimable_rewards)

    def get_current_rewards_price(self) -> Decimal:
        """Get price of Sushi in ETH.

        Returns:
            Decimal: Price per Sushi denominated in ETH
        """
        return Decimal(
            self.sushi_eth_oracle.functions.latestRoundData().call()[1]
            / 10 ** self.sushi_decimals
        )

    def __process_tend(
        self,
        strategy: contract,
        sett_name: str,
        overrides: dict,
        tended: Decimal,
    ):
        """Private function to create, broadcast, confirm tx on eth and then send
        transaction to Discord for monitoring

        Args:
            strategy (contract, optional): Defaults to None.
            sett_name (str, optional): Defaults to None.
            overrides (dict, optional): Dictionary settings for transaction. Defaults to None.
            tended (Decimal, optional): Amount of Sushi tended. Defaults to None.
        """
        error = None
        try:
            tx_hash = self.__send_tend_tx(strategy, overrides)
            succeeded = self.confirm_transaction(tx_hash)
        except Exception as e:
            self.logger.error(f"Error processing tend tx: {e}")
            tx_hash = "invalid" if tx_hash == HexBytes(0) else tx_hash
            succeeded = False
            error = e
        finally:
            succeeded = self.confirm_transaction(tx_hash)
            if succeeded:
                gas_price_of_tx = self._SushiHarvester__get_gas_price_of_tx(tx_hash)
                send_success_to_discord(
                    tx_hash, sett_name, gas_price_of_tx, tended, "Tend"
                )
            elif tx_hash:
                send_error_to_discord(sett_name, "Tend", tx_hash=tx_hash)

    def __send_tend_tx(self, contract: contract, overrides: dict) -> HexBytes:
        """Sends transaction to ETH node for confirmation.

        Args:
            contract (contract)
            overrides (dict)

        Raises:
            Exception: If we have an issue sending transaction (unable to communicate with
            node, etc.) we log the error and return a tx_hash of 0x00.

        Returns:
            HexBytes: Transaction hash for transaction that was sent.
        """
        try:
            tx = contract.functions.tend().buildTransaction(
                {
                    "nonce": self.web3.eth.get_transaction_count(self.keeper_address),
                    "gasPrice": self._SushiHarvester__get_gas_price(),
                    "gas": 12000000,
                    "from": self.keeper_address,
                }
            )
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.keeper_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except Exception as e:
            self.logger.error(f"Error in sending tend tx: {e}")
            tx_hash = HexBytes(0)
            raise Exception
        finally:
            return tx_hash
