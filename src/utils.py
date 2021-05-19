from decimal import Decimal
from discord import Webhook, RequestsWebhookAdapter, Embed
from hexbytes import HexBytes
import os


def send_harvest_error_to_discord(
    sett_name: str, tx_hash: HexBytes = None, error: Exception = None
):
    webhook = Webhook.from_url(
        os.getenv("DISCORD_WEBHOOK_URL"), adapter=RequestsWebhookAdapter()
    )

    embed = Embed(
        title=f"**Harvest Failed for {sett_name}**",
        description=f"{sett_name} Sett Harvest Details",
    )
    message = "Transaction timed out."
    if error:
        message = str(error)
    embed.add_field(name="Failure information", value=message, inline=True)

    webhook.send(embed=embed, username=f"{sett_name} Harvester")


def send_harvest_success_to_discord(
    tx_hash: HexBytes, sett_name: str, gas_cost: Decimal, harvested_amt: Decimal
):
    webhook = Webhook.from_url(
        os.getenv("DISCORD_WEBHOOK_URL"), adapter=RequestsWebhookAdapter()
    )
    embed = Embed(
        title=f"**Badger Harvest Report**",
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
                "value": harvested_amt,
                "inline": True,
            },
        ],
    )
    webhook.send(embed=embed, username=f"{sett_name} Harvester")
