import json
from decimal import Decimal
from typing import Optional

from discord import Embed
from discord import InvalidArgument
from discord import RequestsWebhookAdapter
from discord import Webhook
from hexbytes import HexBytes

from config.constants import CRITICAL_VAULTS
from config.constants import ETH_BVECVX_STRATEGY
from config.enums import Network
from src.aws import get_secret
from src.utils import get_explorer
from src.utils import logger


def send_critical_error_to_discord(
    sett_name: str,
    tx_type: str,
    chain: str = None,
) -> None:
    webhook_url = get_secret(
        "keepers/critical-alert-webhook", "DISCORD_WEBHOOK_URL"
    )
    try:
        webhook = Webhook.from_url(
            webhook_url,
            adapter=RequestsWebhookAdapter(),
        )
    except InvalidArgument:
        logger.error("Discord Webhook URL is not configured")
        return
    message = f"Operation {tx_type} failed for Sett {sett_name} " \
              f"{CRITICAL_VAULTS[ETH_BVECVX_STRATEGY]}"
    webhook.send(content=message, username=f"{chain} {sett_name} {tx_type}er")


def send_error_to_discord(
    sett_name: str,
    tx_type: str,
    tx_hash: HexBytes = None,
    error: Exception = None,
    message: str = "Transaction timed out.",
    chain: str = None,
    keeper_address: str = None,
    webhook_url: Optional[str] = None,
) -> None:
    try:
        if webhook_url:
            webhook = Webhook.from_url(
                webhook_url,
                adapter=RequestsWebhookAdapter(),
            )
        else:
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
