from decimal import Decimal
from discord import Webhook, RequestsWebhookAdapter, Embed
import os

def send_transaction_to_discord(
    tx_hash, 
    sett_name: str,
    amount: Decimal, 
    success: bool,
    error: Exception = None
):
    webhook = Webhook.from_url(os.getenv("DISCORD_WEBHOOK_URL"), adapter=RequestsWebhookAdapter())
    etherscan_url = f"https://etherscan.io/tx/{tx_hash}"

    if success:
        embed = Embed(title=f"**Keeper transaction for {sett_name} SUCCESS**")
        embed.add_field(
            name="Etherscan Transaction", 
            value=f"{etherscan_url}", 
            inline=False
        )
    else:
        embed = Embed(title=f"**Keeper transaction for {sett_name} FAILED**")
        message = f"Transaction {tx_hash} timed out."
        if error:
            message = str(error)
        embed.add_field(name="Failure information", value=message, inline=False)
    
    embed.add_field(
        name="Keeper Action", 
        value=f"Harvest ${str(round(amount))} for sett {sett_name}.", 
        inline=False
    )
    webhook.send(
        embed=embed, 
        username=f"{sett_name} Harvester"
    )