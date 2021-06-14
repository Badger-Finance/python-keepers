from decimal import Decimal
from discord import Webhook, RequestsWebhookAdapter, Embed
from hexbytes import HexBytes
import os


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
        description=f"{sett_name} Sett Harvest Details",
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
    webhook.send(embed=embed, username=f"{sett_name} Harvester")
