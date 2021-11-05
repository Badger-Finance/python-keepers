import boto3
import base64
from botocore.exceptions import ClientError
from decimal import Decimal
from discord import Webhook, RequestsWebhookAdapter, Embed
from hexbytes import HexBytes
import json
import logging
from web3 import Web3, contract, exceptions
import requests
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from constants import MULTICHAIN_CONFIG, SECONDS_IN_A_DAY, BLOCKS_IN_A_DAY

logger = logging.getLogger("utils")


def get_secret(
    secret_name: str, secret_key: str, region_name: str = "us-west-1"
) -> str:
    """Retrieves secret from AWS secretsmanager.
    Args:
        secret_name (str): secret name in secretsmanager
        secret_key (str): Dict key value to use to access secret value
        region_name (str, optional): AWS region name for secret. Defaults to "us-west-1".
    Raises:
        e: DecryptionFailureException - Secrets Manager can't decrypt the protected secret text using the provided KMS key.
        e: InternalServiceErrorException - An error occurred on the server side.
        e: InvalidParameterException - You provided an invalid value for a parameter.
        e: InvalidRequestException - You provided a parameter value that is not valid for the current state of the resource.
        e: ResourceNotFoundException - We can't find the resource that you asked for.
    Returns:
        str: secret value
    """

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=region_name,
    )

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "DecryptionFailureException":
            raise e
        elif e.response["Error"]["Code"] == "InternalServiceErrorException":
            raise e
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            raise e
        elif e.response["Error"]["Code"] == "InvalidRequestException":
            raise e
        elif e.response["Error"]["Code"] == "ResourceNotFoundException":
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if "SecretString" in get_secret_value_response:
            return json.loads(get_secret_value_response["SecretString"]).get(secret_key)
        else:
            return base64.b64decode(get_secret_value_response["SecretBinary"]).get(
                secret_key
            )

    return None


# TODO: Don't duplicate common abis for all chains
def get_abi(chain: str, contract_id: str):
    with open(f"./abi/{chain}/{contract_id}.json") as f:
        return json.load(f)


def hours(num_hours: int) -> int:
    """Returns duration of num_hours in seconds

    Args:
        num_hours (int): Number of hours to represent

    Returns:
        int: Number of seconds num_hours represents
    """
    return 3600 * num_hours


def send_error_to_discord(
    sett_name: str,
    tx_type: str,
    tx_hash: HexBytes = None,
    error: Exception = None,
    message: str = "Transaction timed out.",
    chain: str = None,
    keeper_address: str = None,
):
    try:
        webhook = Webhook.from_url(
            get_secret("keepers/alerts-webhook", "DISCORD_WEBHOOK_URL"),
            adapter=RequestsWebhookAdapter(),
        )

        embed = Embed(
            title=f"**{tx_type} Failed for {sett_name}**",
            description=f"{sett_name} Sett {tx_type} Details",
        )
        if chain:
            embed.add_field(name="Chain", value=chain, inline=True)
        if keeper_address:
            embed.add_field(name="Keeper", value=keeper_address, inline=True)
        if error:
            message = str(error)
        embed.add_field(name="Failure information", value=message, inline=True)

        webhook.send(embed=embed, username=f"{sett_name} {tx_type}er")

    except Exception as e:
        logger.error(f"Error sending error to discord: {e}")


def send_success_to_discord(
    tx_hash: HexBytes,
    tx_type: str,
    gas_cost: Decimal = None,
    amt: Decimal = None,
    sett_name: str = None,
    chain: str = "ETH",
    url: str = None,
):
    try:
        if not url:
            url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")

        webhook = Webhook.from_url(
            url,
            adapter=RequestsWebhookAdapter(),
        )

        status = "Completed" if gas_cost else "Pending"

        (explorer_name, explorer_url) = get_explorer(chain, tx_hash)

        # init embed object
        if tx_type in ["Harvest", "Tend"]:
            embed = Embed(
                title=f"**Badger {tx_type} Report**",
                description=f"{sett_name} Sett {tx_type} Details",
            )
        else:
            embed = Embed(
                title=f"**Badger {tx_type} Report**",
                description=f"{status} {tx_type}",
            )

        fields = []
        # append link to tx scan website
        fields.append(
            {
                "name": f"{explorer_name} Transaction",
                "value": explorer_url,
                "inline": False,
            }
        )
        # append gas cost if tx finished
        if status == "Completed":
            fields.append(
                {
                    "name": "Gas Cost",
                    "value": f"${round(gas_cost, 2)}",
                    "inline": True,
                }
            )
        # add amount harvested / tended
        if tx_type in ["Harvest", "Tend"]:
            fields.append(
                {
                    "name": f"Amount {tx_type}ed",
                    "value": amt,
                    "inline": True,
                }
            )

        for field in fields:
            embed.add_field(
                name=field.get("name"),
                value=field.get("value"),
                inline=field.get("inline"),
            )

        if tx_type in ["Harvest", "Tend"]:
            webhook.send(embed=embed, username=f"{sett_name} {tx_type}er")
        else:
            webhook.send(embed=embed, username=f"{tx_type}")

    except Exception as e:
        logger.error(f"Error sending success to discord: {e}")


def send_rebase_to_discord(tx_hash: HexBytes, gas_cost: Decimal = None):
    webhook = Webhook.from_url(
        get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL"),
        adapter=RequestsWebhookAdapter(),
    )
    status = "Completed" if gas_cost else "Pending"
    fields = [
        {
            "name": "Etherscan Transaction",
            "value": f"https://etherscan.io/tx/{tx_hash.hex()}",
            "inline": False,
        }
    ]
    if status == "Completed":
        fields.append(
            {
                "name": "Gas Cost",
                "value": f"${round(gas_cost, 2)}",
                "inline": True,
            }
        )
    # TODO: have supply change represented
    # {
    #     "name": "Supply Change",
    #     "value": amt,
    #     "inline": True,
    # }
    embed = Embed(
        title=f"**Badger Rebaser Report**",
        description=f"{status} Rebase",
    )
    for field in fields:
        embed.add_field(
            name=field.get("name"), value=field.get("value"), inline=field.get("inline")
        )
    webhook.send(embed=embed, username=f"Rebaser")


def send_rebase_error_to_discord(error: Exception):
    webhook = Webhook.from_url(
        get_secret("keepers/alerts-webhook", "DISCORD_WEBHOOK_URL"),
        adapter=RequestsWebhookAdapter(),
    )
    embed = Embed(
        title=f"**Badger Rebaser Report**",
        description=f"Failed Rebase",
    )
    embed.add_field(name="Error sending rebase tx", value=f"{error}", inline=False)
    webhook.send(embed=embed, username=f"Rebaser")


def send_oracle_error_to_discord(tx_type: str, error: Exception):
    webhook = Webhook.from_url(
        get_secret("keepers/alerts-webhook", "DISCORD_WEBHOOK_URL"),
        adapter=RequestsWebhookAdapter(),
    )
    embed = Embed(
        title=f"**Badger {tx_type} Report**",
        description=f"Failed {tx_type}",
    )
    embed.add_field(name=f"Error sending {tx_type} tx", value=f"{error}", inline=False)
    webhook.send(embed=embed, username=f"{tx_type}")


def confirm_transaction(
    web3: Web3, tx_hash: HexBytes, timeout: int = 120, max_block: int = None
) -> tuple[bool, str]:
    """Waits for transaction to appear within a given timeframe or before a given block (if specified), and then times out.

    Args:
        web3 (Web3): Web3 instance
        tx_hash (HexBytes): Transaction hash to identify transaction to wait on.
        timeout (int, optional): Timeout in seconds. Defaults to 60.
        max_block (int, optional): Max block number to wait until. Defaults to None.

    Returns:
        bool: True if transaction was confirmed, False otherwise.
        msg: Log message.
    """
    logger.info(f"tx_hash before confirm: {tx_hash.hex()}")

    while True:
        try:
            web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            msg = f"Transaction {tx_hash.hex()} succeeded!"
            logger.info(msg)
            return True, msg
        except exceptions.TimeExhausted:
            if max_block is None or web3.eth.block_number > max_block:
                if max_block is None:
                    msg = f"Transaction {tx_hash.hex()} timed out, not included in block yet."
                else:
                    msg = f"Transaction {tx_hash.hex()} was not included in the block."
                logger.error(msg)
                return False, msg
            else:
                continue
        except Exception as e:
            msg = f"Error waiting for {tx_hash.hex()}. Error: {e}."
            logger.error(msg)
            return False, msg


def get_hash_from_failed_tx_error(
    error: ValueError,
    tx_type: str,
    sett_name: str = None,
    chain: str = None,
    keeper_address: str = None,
) -> HexBytes:
    try:
        error_obj = json.loads(str(error).replace("'", '"'))
        send_error_to_discord(
            tx_type=tx_type,
            sett_name=sett_name,
            error=error_obj,
            chain=chain,
            keeper_address=keeper_address,
        )
        tx_hash = list(error_obj.get("data").keys())[0]
    except Exception as x:
        logger.error(f"exception when trying to get tx_hash: {x}")
        tx_hash = HexBytes(0)
    finally:
        return tx_hash


def get_explorer(chain: str, tx_hash: HexBytes) -> tuple:
    if chain.lower() == "eth":
        explorer_name = "Etherscan"
        explorer_url = f"https://etherscan.io/tx/{tx_hash.hex()}"
    elif chain.lower() == "bsc":
        explorer_name = "Bscscan"
        explorer_url = f"https://bscscan.io/tx/{tx_hash.hex()}"
    elif chain.lower() == "poly":
        explorer_name = "Polygonscan"
        explorer_url = f"https://polygonscan.com/tx/{tx_hash.hex()}"
    elif chain.lower() == "arbitrum":
        explorer_name = "Arbiscan"
        explorer_url = f"https://arbiscan.io/tx/{tx_hash.hex()}"

    return (explorer_name, explorer_url)


def get_last_harvest_times(
    web3: Web3, keeper_acl: contract, start_block: int = 0, etherscan_key: str = None
):
    """Fetches the latest harvest timestamps of strategies from Etherscan API which occur after `start_block`.
    NOTE: Temporary function until Harvested events are emitted from all strategies.

    Args:
        web3 (Web3): Web3 node instance.
        keeper_acl (contract): Keeper ACL web3 contract instance.
        start_block (int, optional): Minimum block number to start fetching harvest timestamps from. Defaults to 0.

    Returns:
        dict: Dictionary of strategy addresses and their latest harvest timestamps.
    """
    if etherscan_key is None:
        etherscan_key = get_secret("keepers/etherscan", "ETHERSCAN_TOKEN")

    endpoint = "https://api.etherscan.io/api"
    payload = {
        "module": "account",
        "action": "txlist",
        "address": keeper_acl.address,
        "startblock": start_block,
        "endblock": web3.eth.block_number,
        "sort": "desc",
        "apikey": etherscan_key,
    }
    try:
        response = requests.get(endpoint, params=payload)
        response.raise_for_status()  # Raise HTTP errors

        data = response.json()
        times = {}
        for tx in data["result"]:
            if (
                tx["to"] == ""
                or web3.toChecksumAddress(tx["to"]) != keeper_acl.address
                or "input" not in tx
            ):
                continue
            fn, args = keeper_acl.decode_function_input(tx["input"])
            if (
                str(fn)
                in [
                    "<Function harvest(address)>",
                    "<Function harvestNoReturn(address)>",
                ]
                and args["strategy"] not in times
            ):
                times[args["strategy"]] = int(tx["timeStamp"])
            elif (
                str(fn) == "<Function harvestMta(address)>"
                and args["voterProxy"] not in times
            ):
                times[args["voterProxy"]] = int(tx["timeStamp"])
        return times
    except (KeyError, requests.HTTPError):
        raise ValueError("Last harvest time couldn't be fetched")


# TODO: move to own utils func and separate utils.py into directory and sub classes
def get_strategies_from_registry(node: Web3, chain: str) -> list:
    strategies = []

    registry = node.eth.contract(
        address=node.toChecksumAddress(MULTICHAIN_CONFIG[chain]["registry"]),
        abi=get_abi(chain, "registry"),
    )

    for vault_owner in MULTICHAIN_CONFIG[chain]["vault_owner"]:
        vault_owner = node.toChecksumAddress(vault_owner)

        for vault_address in registry.functions.getVaults("v1", vault_owner).call():
            strategy, _ = get_strategy_from_vault(node, chain, vault_address)
            strategies.append(strategy)

    return strategies


def get_strategy_from_vault(
    node: Web3, chain: str, vault_address: str
) -> (contract, contract):
    vault_contract = node.eth.contract(
        address=vault_address, abi=get_abi(chain, "vault")
    )

    token_address = vault_contract.functions.token().call()
    controller_address = vault_contract.functions.controller().call()

    controller_contract = node.eth.contract(
        address=controller_address, abi=get_abi(chain, "controller")
    )

    strategy_address = controller_contract.functions.strategies(token_address).call()

    # TODO: handle v1 vs v2 strategy abi
    strategy_contract = node.eth.contract(
        address=strategy_address, abi=get_abi(chain, "strategy")
    )

    return strategy_contract, vault_contract


def get_strategies_and_vaults(node: Web3, chain: str) -> list:
    strategies = []
    vaults = []

    registry = node.eth.contract(
        address=node.toChecksumAddress(MULTICHAIN_CONFIG.get(chain).get("registry")),
        abi=get_abi(chain, "registry"),
    )

    for vault_owner in MULTICHAIN_CONFIG[chain]["vault_owner"]:
        vault_owner = node.toChecksumAddress(vault_owner)

        for vault_address in registry.functions.getVaults("v1", vault_owner).call():
            strategy, vault = get_strategy_from_vault(node, chain, vault_address)
            vaults.append(vault)
            strategies.append(strategy)

    return strategies, vaults


def seconds_to_blocks(seconds: int) -> int:
    return seconds / SECONDS_IN_A_DAY * BLOCKS_IN_A_DAY


def get_price_per_want(want_address: str, chain: str) -> int:
    prices = requests.get(
        f"https://api.badger.finance/v2/prices?currency={chain}"
    ).json()
    price_per_want_eth = prices.get(want_address, 0)
    logger.info(f"price per want: {price_per_want_eth}")
    return price_per_want_eth
