import base64
import json
import logging
import os
from decimal import Decimal
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from discord import Embed
from discord import RequestsWebhookAdapter
from discord import Webhook
from hexbytes import HexBytes

from config.constants import ABI_DIRS
from config.constants import NODE_URL_SECRET_NAMES
from config.enums import Network

logger = logging.getLogger(__name__)

AWS_ERR_CODES = [
    "DecryptionFailureException",
    "InternalServiceErrorException",
    "InvalidParameterException",
    "ResourceNotFoundException",
]


def get_secret(
    secret_name: str, secret_key: str, region_name: str = "us-west-1"
) -> Optional[str]:
    """Retrieves secret from AWS secretsmanager.
    Args:
        secret_name (str): secret name in secretsmanager
        secret_key (str): Dict key value to use to access secret value
        region_name (str, optional): AWS region name for secret. Defaults to "us-west-1".
    Raises:
        e: DecryptionFailureException - Secrets Manager can't decrypt
            the protected secret text using the provided KMS key.
        e: InternalServiceErrorException - An error occurred on the server side.
        e: InvalidParameterException - You provided an invalid value for a parameter.
        e: InvalidRequestException - You provided a parameter value
            that is not valid for the current state of the resource.
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
        if e.response["Error"]["Code"] in AWS_ERR_CODES:
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string
        # or binary, one of these fields will be populated.
        if "SecretString" in get_secret_value_response:
            return json.loads(get_secret_value_response["SecretString"]).get(secret_key)
        else:
            return json.loads(base64.b64decode(
                get_secret_value_response["SecretBinary"]
            ).decode(
                "utf-8"
            )).get(
                secret_key
            )


def get_node_url(chain) -> str:
    secret_name = NODE_URL_SECRET_NAMES[chain]["name"]
    secret_key = NODE_URL_SECRET_NAMES[chain]["key"]
    url = get_secret(secret_name, secret_key)
    return url


# TODO: Don't duplicate common abis for all chains
def get_abi(chain: str, contract_id: str):
    project_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(f"{project_root_dir}/abi/{ABI_DIRS[chain]}/{contract_id}.json") as f:
        return json.load(f)


def send_error_to_discord(
    sett_name: str,
    tx_type: str,
    tx_hash: HexBytes = None,
    error: Exception = None,
    message: str = "Transaction timed out.",
    chain: str = None,
    keeper_address: str = None,
) -> None:
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
    chain: str = Network.Ethereum,
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
        title="**Badger Rebaser Report**",
        description=f"{status} Rebase",
    )
    for field in fields:
        embed.add_field(
            name=field.get("name"), value=field.get("value"), inline=field.get("inline")
        )
    webhook.send(embed=embed, username="Rebaser")


def send_rebase_error_to_discord(error: Exception):
    webhook = Webhook.from_url(
        get_secret("keepers/alerts-webhook", "DISCORD_WEBHOOK_URL"),
        adapter=RequestsWebhookAdapter(),
    )
    embed = Embed(
        title="**Badger Rebaser Report**",
        description="Failed Rebase",
    )
    embed.add_field(name="Error sending rebase tx", value="{error}", inline=False)
    webhook.send(embed=embed, username="Rebaser")


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


def get_hash_from_failed_tx_error(
    error: ValueError,
    tx_type: str,
    sett_name: str = None,
    chain: str = None,
    keeper_address: str = None,
) -> Optional[HexBytes]:
    tx_hash = None
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


def get_explorer(chain: Network, tx_hash: HexBytes) -> Optional[tuple[str, str]]:
    if chain == Network.Ethereum:
        explorer_name = "Etherscan"
        explorer_url = f"https://etherscan.io/tx/{tx_hash.hex()}"
    elif chain == Network.Polygon:
        explorer_name = "Polygonscan"
        explorer_url = f"https://polygonscan.com/tx/{tx_hash.hex()}"
    elif chain == Network.Arbitrum:
        explorer_name = "Arbiscan"
        explorer_url = f"https://arbiscan.io/tx/{tx_hash.hex()}"
    elif chain == Network.Fantom:
        explorer_name = "Ftmscan"
        explorer_url = f"https://ftmscan.com/tx/{tx_hash.hex()}"
    else:
        return None

    return explorer_name, explorer_url
