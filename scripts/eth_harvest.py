import time

from web3 import Web3
from web3 import contract

from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import ETH_KEEPER_ACL
from config.constants import ETH_SLP_BADGER_WBTC_STRATEGY
from config.constants import GWEI_150
from config.constants import GWEI_80
from config.constants import MULTICHAIN_CONFIG
from config.constants import SECONDS_PER_BLOCK
from config.enums import Network
from src.aws import get_secret
from src.data_classes.contract import Contract
from src.general_harvester import GeneralHarvester
from src.json_logger import logger
from src.misc_utils import hours
from src.misc_utils import seconds_to_blocks
from src.settings.harvest_settings import ETH_HARVEST_SETTINGS
from src.tx_utils import get_latest_base_fee
from src.utils import get_abi
from src.web3_utils import get_last_harvest_times
from src.web3_utils import get_strategies_and_vaults

HOURS_24 = hours(24)
HOURS_72 = hours(72)
HOURS_96 = hours(96)
HOURS_120 = hours(120)

BLOCKS_TO_SLEEP = 2

rewards_manager_strategies = {ETH_SLP_BADGER_WBTC_STRATEGY}


def conditional_harvest(harvester: GeneralHarvester, strategy: Contract) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)
    logger.info(f"Checking harvests for {strategy.name} {strategy.address}")

    if harvester.is_time_to_harvest(
        strategy.contract, HOURS_96
    ) and latest_base_fee < int(GWEI_80):
        logger.info(f"Been longer than 96 hours and base fee < 80 for {strategy.name}")
        res = safe_harvest(harvester, strategy)
        logger.info(res)
    elif harvester.is_time_to_harvest(strategy.contract) and latest_base_fee < int(
        GWEI_150
    ):
        logger.info(
            f"Been longer than 120 hours harvest no matter what for {strategy.name}"
        )
        res = safe_harvest(harvester, strategy)
        logger.info(res)


def conditional_harvest_rewards_manager(
    harvester: GeneralHarvester, strategy_name: str, strategy: contract
) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)

    # regular thresholds for rest of vaults
    if harvester.is_time_to_harvest(strategy, HOURS_96) and latest_base_fee < int(
        GWEI_80
    ):
        logger.info(f"Been longer than 96 hours and base fee < 80 for {strategy_name}")
        logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
        try:
            harvester.harvest_rewards_manager(strategy)
        except Exception as e:
            logger.error(f"Error running {strategy_name} harvest: {e}")
    elif harvester.is_time_to_harvest(strategy) and latest_base_fee < int(GWEI_150):
        logger.info(
            f"Been longer than 120 hours harvest no matter what for {strategy_name}"
        )
        logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
        try:
            harvester.harvest_rewards_manager(strategy)
        except Exception as e:
            logger.error(f"Error running {strategy_name} harvest: {e}")


def safe_harvest(harvester: GeneralHarvester, strategy: Contract) -> str:
    logger.info(f"+-----Harvesting {strategy.name} {strategy.address}-----+")

    try:
        harvester.harvest(strategy.contract, strategy_name=strategy.name)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy.name} harvest: {e}")


if __name__ == "__main__":
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = "https://rpc.flashbots.net"
    discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=ETH_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        use_flashbots=False,
        discord_url=discord_url,
    )

    strategies, vaults = get_strategies_and_vaults(web3, Network.Ethereum)

    to_harvest = {
        vault.address: strategy for strategy, vault in zip(strategies, vaults)
    }

    for vault_address in to_harvest.keys():
        if (
            # Restitution vaults (rembadger) don't have underlying strategy, waste of gas
            vault_address not in ETH_HARVEST_SETTINGS.restitution_vaults
            # Rewards manager vaults have to be handled separately
            and vault_address not in ETH_HARVEST_SETTINGS.rewards_manager_vaults
        ):
            strategy: Contract = to_harvest[vault_address]
            conditional_harvest(harvester, strategy)

            # Sleep for 2 blocks in between harvests
            time.sleep(BLOCKS_TO_SLEEP * SECONDS_PER_BLOCK)

    # Harvest rewards manager strategies
    rewards_manager = harvester.web3.eth.contract(
        address=harvester.web3.toChecksumAddress(
            MULTICHAIN_CONFIG[harvester.chain]["rewards_manager"]
        ),
        abi=get_abi(harvester.chain, "rewards_manager"),
    )

    harvester.last_harvest_times = get_last_harvest_times(
        harvester.web3,
        rewards_manager,
        start_block=harvester.web3.eth.block_number - seconds_to_blocks(HOURS_120),
    )

    for strategy_address in rewards_manager_strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Ethereum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        conditional_harvest_rewards_manager(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(BLOCKS_TO_SLEEP * SECONDS_PER_BLOCK)
