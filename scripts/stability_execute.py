import logging

from eth_account.account import Account
from web3 import Web3

from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import ETH_KEEPER_ACL
from config.constants import ETH_STABILIZE_STRATEGY
from config.enums import Network
from src.eth.stability_executor import StabilityExecutor
from src.utils import get_abi
from src.aws import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "NODE_URL")
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )
    # flashbots_signer = Account.create()

    web3 = Web3(Web3.HTTPProvider(node_url))

    strategy = web3.eth.contract(
        address=ETH_STABILIZE_STRATEGY, abi=get_abi(Network.Ethereum, "stability_strat")
    )

    stability_executor = StabilityExecutor(
        web3=web3,
        keeper_acl=ETH_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        use_flashbots=False,
    )

    logger.info("+-----REBALANCING DIGG STABILITY SETT-----+")
    stability_executor.execute_batch(strategy)
