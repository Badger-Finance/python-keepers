import time

from web3 import Web3

from config.constants import FTM_VAULTS_1
from config.constants import FTM_VAULTS_15
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from config.enums import VaultVersion
from src.aws import get_secret
from src.general_harvester import GeneralHarvester
from src.json_logger import logger
from src.misc_utils import hours
from src.web3_utils import get_strategy_from_vault

HOURS_12 = hours(12)


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = "https://rpc.ftm.tools/"
    discord_url = get_secret(
        "keepers/harvester/fantom/info-webhook", "DISCORD_WEBHOOK_URL"
    )

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        chain=Network.Fantom,
        keeper_acl=MULTICHAIN_CONFIG[Network.Fantom]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Fantom]["gas_oracle"],
        use_flashbots=False,
        discord_url=discord_url,
    )
    strategies = []
    for vault_address in FTM_VAULTS_1:
        strategy, _ = get_strategy_from_vault(web3, Network.Fantom, vault_address)
        strategies.append(strategy)

    for vault_address in FTM_VAULTS_15:
        strategy, _ = get_strategy_from_vault(
            web3, Network.Fantom, vault_address, version=VaultVersion.v1_5
        )
        strategies.append(strategy)

    for strategy in strategies:
        if (
            strategy.address
            not in MULTICHAIN_CONFIG[Network.Fantom]["harvest"]["invalid_strategies"]
        ):
            # safe_harvest(harvester, strategy)
            strategy_name = strategy.functions.getName().call()
            logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
            if harvester.is_time_to_harvest(strategy, HOURS_12):
                harvester.harvest(strategy)

            # Sleep for a few blocks in between harvests
            time.sleep(30)
