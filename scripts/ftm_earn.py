import sys

from web3 import Web3

from config.constants import FTM_OXD_BVEOXD_VAULT
from config.constants import FTM_VAULTS_1
from config.constants import FTM_VAULTS_15
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from config.enums import VaultVersion
from src.aws import get_secret
from src.earner import Earner
from src.json_logger import exception_logging
from src.json_logger import logger
from src.web3_utils import get_strategy_from_vault

INVALID_VAULTS = [FTM_OXD_BVEOXD_VAULT]


sys.excepthook = exception_logging


def safe_earn(earner, vault, strategy):
    try:
        sett_name = strategy.functions.getName().call()
        logger.info(f"+-----Earning {sett_name}-----+")
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running earn: {e}")


if __name__ == "__main__":
    for chain in [Network.Fantom]:
        node_url = "https://rpc.ftm.tools/"
        node = Web3(Web3.HTTPProvider(node_url))

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
        discord_url = get_secret(
            "keepers/harvester/fantom/info-webhook", "DISCORD_WEBHOOK_URL"
        )

        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG.get(chain).get("gas_oracle"),
            discord_url=discord_url,
        )
        strategies = []
        vaults = []
        for vault_address in FTM_VAULTS_1:
            if vault_address not in INVALID_VAULTS:
                strategy, vault = get_strategy_from_vault(node, chain, vault_address)
                strategies.append(strategy)
                vaults.append(vault)

        for vault_address in FTM_VAULTS_15:
            if vault_address not in INVALID_VAULTS:
                strategy, vault = get_strategy_from_vault(
                    node, chain, vault_address, version=VaultVersion.v1_5
                )
                strategies.append(strategy)
                vaults.append(vault)

        for strategy, vault in zip(strategies, vaults):
            if (
                strategy.address
                not in MULTICHAIN_CONFIG[chain]["earn"]["invalid_strategies"]
            ):
                sett_name = strategy.functions.getName().call()
                logger.info(f"+-----Earning {sett_name}-----+")
                earner.earn(vault, strategy, sett_name=sett_name)
                # safe_earn(earner, vault, strategy)
