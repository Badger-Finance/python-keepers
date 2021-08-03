import boto3
import base64
from botocore.exceptions import ClientError
from decimal import Decimal
from discord import Webhook, RequestsWebhookAdapter, Embed
from hexbytes import HexBytes
import json
import logging
import os
from web3 import Web3, exceptions
import requests

logger = logging.getLogger()


def hours(num_hours: int) -> int:
    """Returns duration of num_hours in seconds

    Args:
        num_hours (int): Number of hours to represent

    Returns:
        int: Number of seconds num_hours represents
    """
    return 3600 * num_hours


def send_error_to_discord(
    sett_name: str, type: str, tx_hash: HexBytes = None, error: Exception = None
):
    webhook = Webhook.from_url(
        get_secret("keepers/alerts-webhook", "DISCORD_WEBHOOK_URL"),
        adapter=RequestsWebhookAdapter(),
    )

    embed = Embed(
        title=f"**{type} Failed for {sett_name}**",
        description=f"{sett_name} Sett {type} Details",
    )
    message = "Transaction timed out."
    if error:
        message = str(error)
    embed.add_field(name="Failure information", value=message, inline=True)

    webhook.send(embed=embed, username=f"{sett_name} {type}er")


def send_success_to_discord(
    tx_hash: HexBytes,
    tx_type: str,
    gas_cost: Decimal = None,
    amt: Decimal = None,
    sett_name: str = None,
    chain: str = "ETH",
):
    webhook = Webhook.from_url(
        get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL"),
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
            name=field.get("name"), value=field.get("value"), inline=field.get("inline")
        )

    if tx_type in ["Harvest", "Tend"]:
        webhook.send(embed=embed, username=f"{sett_name} {tx_type}er")
    else:
        webhook.send(embed=embed, username=f"{tx_type}")


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


def confirm_transaction(web3: Web3, tx_hash: HexBytes, target_block: int=None) -> bool:
    """Waits for transaction to appear in block for 60 seconds and then times out.

    Args:
        tx_hash (HexBytes): Transaction hash to identify transaction to wait on.

    Returns:
        bool: True if transaction was confirmed in 60 seconds, False otherwise.
    """
    logger.info(f"tx_hash before confirm: {tx_hash.hex()}")

    while True:
        try:
            web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            break
        except exceptions.TimeExhausted:
            if target_block is None:
                logger.error(
                    f"Transaction {tx_hash.hex()} timed out, not included in block yet."
                )
                return False
            elif web3.eth.block_number > target_block:
                logger.error(f"Transaction was not included in the block.")
                return False
        except Exception as e:
            logger.error(f"Error waiting for {tx_hash.hex()}. Error: {e}.")
            return False

    logger.info(f"Transaction {tx_hash.hex()} succeeded!")
    return True


def get_hash_from_failed_tx_error(
    error: ValueError, logger: logging.Logger
) -> HexBytes:
    try:
        error_obj = json.loads(str(error).replace("'", '"'))
        send_rebase_error_to_discord(error=error_obj)
        tx_hash = list(error_obj.get("data").keys())[0]
    except Exception as x:
        logger.error(f"exception when trying to get tx_hash: {x}")
        tx_hash = HexBytes(0)
    finally:
        return tx_hash


def get_explorer(chain: str, tx_hash: HexBytes) -> tuple:
    if chain == "ETH":
        explorer_name = "Etherscan"
        explorer_url = f"https://etherscan.io/tx/{tx_hash.hex()}"
    elif chain == "BSC":
        explorer_name = "Bscscan"
        explorer_url = f"https://bscscan.io/tx/{tx_hash.hex()}"
    return (explorer_name, explorer_url)


def get_coingecko_price(token_address: str, base="usd") -> float:
    """Fetches the price of token in USD/ETH from CoinGecko API.

    Args:
        token_address (str): Contract address of the ERC-20 token to get price for.

    Returns:
        float: Price of token in base currency.
    """
    endpoint = "https://api.coingecko.com/api/v3/"
    try:
        params = "/simple/supported_vs_currencies"
        r = requests.get(endpoint + params)

        supported_bases = r.json()
        if base not in supported_bases:
            raise ValueError("Unsupported base currency")

        params = (
            "simple/token_price/ethereum?contract_addresses="
            + token_address
            + "&vs_currencies=eth%2Cusd&include_last_updated_at=true"
        )
        r = requests.get(endpoint + params)
        data = r.json()
        return data[token_address.lower()][base]

    except (KeyError, requests.HTTPError):
        raise ValueError("Price could not be fetched")