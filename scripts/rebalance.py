import logging

from eth_account.account import Account

from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import ETH_KEEPER_ACL
from config.constants import ETH_STABILIZE_STRATEGY
from config.enums import Network
from src.aws import get_secret
from src.eth.rebalancer import Rebalancer
from src.utils import get_abi
from src.utils import get_healthy_node

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    web3 = get_healthy_node(Network.Ethereum)
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )

    strategy = web3.eth.contract(
        address=ETH_STABILIZE_STRATEGY, abi=get_abi(Network.Ethereum, "stability_strat")
    )

    rebalancer = Rebalancer(
        web3=web3,
        keeper_acl=ETH_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        use_flashbots=False,
    )

    logger.info("+-----REBALANCING DIGG STABILITY SETT-----+")
    rebalancer.rebalance(strategy)
