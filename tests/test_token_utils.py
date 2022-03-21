import pytest
import responses
from requests import HTTPError

from config.enums import Network
from src.token_utils import get_token_price


@responses.activate
def test_get_token_price_prod():
    currency = "usd"
    price = 8.75
    responses.add(
        responses.GET,
        f"https://api.badger.finance/v2/prices?currency={currency}&chain={Network.Ethereum}",
        json={
            "0x3472a5a71965499acd81997a54bba8d852c6e53d": 8.75,
        },
        status=200,
    )
    token_price = get_token_price(
        token_address="0x3472a5a71965499acd81997a54bba8d852c6e53d",
        currency="usd",
        chain=Network.Ethereum,
    )
    assert token_price == price


@responses.activate
def test_get_token_price_staging():
    currency = "usd"
    price = 8.75
    responses.add(
        responses.GET,
        f"https://staging-api.badger.finance/v2/prices?currency={currency}"
        f"&chain={Network.Ethereum}",
        json={
            "0x3472a5a71965499acd81997a54bba8d852c6e53d": 8.75,
        },
        status=200,
    )
    token_price = get_token_price(
        token_address="0x3472a5a71965499acd81997a54bba8d852c6e53d",
        currency="usd",
        chain=Network.Ethereum,
        use_staging=True,
    )
    assert token_price == price


@responses.activate
def test_get_token_price_raises():
    currency = "usd"
    responses.add(
        responses.GET,
        f"https://staging-api.badger.finance/v2/prices?currency={currency}"
        f"&chain={Network.Ethereum}",
        json={
            "0x3472a5a71965499acd81997a54bba8d852c6e53d": 8.75,
        },
        status=403,
    )
    with pytest.raises(HTTPError):
        get_token_price(
            token_address="0x3472a5a71965499acd81997a54bba8d852c6e53d",
            currency="usd",
            chain=Network.Ethereum,
            use_staging=True,
        )
