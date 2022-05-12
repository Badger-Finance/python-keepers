from decimal import Decimal

from discord import InvalidArgument
from hexbytes import HexBytes

from src.discord_utils import send_critical_error_to_discord
from src.discord_utils import send_error_to_discord
from src.discord_utils import send_oracle_error_to_discord
from src.discord_utils import send_rebase_error_to_discord
from src.discord_utils import send_rebase_to_discord
from src.discord_utils import send_success_to_discord


def test_send_critical_error_to_discord_send_called(mocker):
    secret = mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")
    send_critical_error_to_discord(
        sett_name="whatever",
        tx_type="whatever",
        chain="Ethereum",
    )
    assert webhook.return_value.send.called
    assert secret.called


def test_send_critical_error_to_discord_send_not_called_invalid_url(mocker):
    mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url", side_effect=InvalidArgument)
    send_critical_error_to_discord(
        sett_name="whatever",
        tx_type="whatever",
        chain="Ethereum",
    )
    assert not webhook.return_value.send.called


def test_send_error_to_discord_send_called(mocker):
    secret = mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")
    send_error_to_discord(
        sett_name="whatever",
        tx_type="whatever",
        tx_hash=HexBytes("0x123123"),
    )
    assert webhook.return_value.send.called
    assert secret.called


def test_send_error_to_discord_send_secret_not_called_url_provided(mocker):
    secret = mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")
    send_error_to_discord(
        sett_name="whatever",
        tx_type="whatever",
        tx_hash=HexBytes("0x123123"),
        webhook_url="some_hook"
    )
    assert webhook.return_value.send.called
    assert not secret.return_value.called
    assert not secret.called


def test_send_success_to_discord_send_called(mocker):
    mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")

    send_success_to_discord(
        tx_hash=HexBytes("0x123123"),
        tx_type="Harvest",
        gas_cost=Decimal(123),
    )
    assert webhook.return_value.send.called


def test_send_rebase_to_discord_send_called(mocker):
    mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")

    send_rebase_to_discord(tx_hash=HexBytes("0x123123"), gas_cost=Decimal(123.0))
    assert webhook.return_value.send.called


def test_send_rebase_error_to_discord_send_called(mocker):
    mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")

    send_rebase_error_to_discord(Exception())
    assert webhook.return_value.send.called


def test_send_oracle_error_to_discord_send_called(mocker):
    mocker.patch("src.discord_utils.get_secret")
    mocker.patch("src.discord_utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.discord_utils.Webhook.from_url")

    send_oracle_error_to_discord(tx_type="whatever", error=Exception())
    assert webhook.return_value.send.called
