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
        os.getenv("DISCORD_WEBHOOK_URL"), adapter=RequestsWebhookAdapter()
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
    tx_hash: HexBytes, sett_name: str, gas_cost: Decimal, amt: Decimal, type: str
):
    webhook = Webhook.from_url(
        os.getenv("DISCORD_WEBHOOK_URL"), adapter=RequestsWebhookAdapter()
    )
    embed = Embed(
        title=f"**Badger {type} Report**",
        description=f"{sett_name} Sett {type} Details",
        fields=[
            {
                "name": "Etherscan Transaction",
                "value": f"https://etherscan.io/tx/${tx_hash.hex()}",
                "inline": False,
            },
            {
                "name": "Gas Cost",
                "value": f"${round(gas_cost, 2)}",
                "inline": True,
            },
            {
                "name": "Amount Harvested",
                "value": amt,
                "inline": True,
            },
        ],
    )
    webhook.send(embed=embed, username=f"{sett_name} {type}er")

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


def confirm_transaction(web3: Web3, tx_hash: HexBytes) -> bool:
    """Waits for transaction to appear in block for 60 seconds and then times out.

    Args:
        tx_hash (HexBytes): Transaction hash to identify transaction to wait on.

    Returns:
        bool: True if transaction was confirmed in 60 seconds, False otherwise.
    """
    try:
        web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    except exceptions.TimeExhausted:
        logger.error(f"Transaction {tx_hash} timed out, not included in block yet.")
        return False

    logger.info(f"Transaction {tx_hash} succeeded!")
    return True