import time

from config.constants import ARB_SWAPR_WBTC_WETH_STRATEGY
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.aws import get_secret
from src.general_harvester import GeneralHarvester
from src.json_logger import logger
from src.utils import get_abi
from src.utils import get_healthy_node

strategies = {ARB_SWAPR_WBTC_WETH_STRATEGY}


def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"HARVESTING strategy {strategy.address}")
    try:
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    web3 = get_healthy_node(Network.Arbitrum)
    discord_url = get_secret(
        "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
    )

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=MULTICHAIN_CONFIG[Network.Arbitrum]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Arbitrum]["gas_oracle"],
        use_flashbots=False,
        discord_url=discord_url,
    )

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Arbitrum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        logger.info(f"+-----Harvesting {strategy_name}-----+")
        safe_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)
