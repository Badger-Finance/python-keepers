from hexbytes import HexBytes

from src.utils import send_error_to_discord


def test_send_error_to_discord(mocker):
    mocker.patch("src.utils.get_secret")
    mocker.patch("src.utils.RequestsWebhookAdapter")
    webhook = mocker.patch("src.utils.Webhook.from_url")
    send_error_to_discord(
        sett_name="whatever",
        tx_type="whatever",
        tx_hash=HexBytes("0x123123"),
    )
    assert webhook.return_value.send.called
