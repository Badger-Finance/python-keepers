import pytest
import responses
from requests import HTTPError

from config.enums import Network
from src.token_utils import get_token_price
from src.token_utils import PriceNotFound


@responses.activate
def test_get_token_price_prod():
    currency = "usd"
    price = 8.75
    responses.add(
        responses.GET,
        f"https://api.badger.com/v2/prices?currency={currency}&chain={Network.Ethereum}",
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
        f"https://staging-api.badger.com/v2/prices?currency={currency}"
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
        f"https://staging-api.badger.com/v2/prices?currency={currency}"
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


@responses.activate
def test_get_token_price_fallback():
    currency = "usd"
    price = 8.75
    responses.add(
        responses.GET,
        f"https://api.badger.com/v2/prices?currency={currency}"
        f"&chain={Network.Ethereum}",
        json={},
        status=200,
    )
    responses.add(
        responses.GET,
        f"https://staging-api.badger.com/v2/prices?currency={currency}"
        f"&chain={Network.Ethereum}",
        json={
            "0x3472a5a71965499acd81997a54bba8d852c6e53d": price,
        },
        status=200,
    )
    token_price = get_token_price(
        token_address="0x3472a5a71965499acd81997a54bba8d852c6e53d",
        currency="usd",
        chain=Network.Ethereum,
        use_staging=False,
    )

    assert token_price == price


@responses.activate
def test_get_token_price_not_found():
    currency = "usd"
    responses.add(
        responses.GET,
        f"https://api.badger.com/v2/prices?currency={currency}"
        f"&chain={Network.Ethereum}",
        json={},
        status=200,
    )
    responses.add(
        responses.GET,
        f"https://staging-api.badger.com/v2/prices?currency={currency}"
        f"&chain={Network.Ethereum}",
        json={},
        status=200,
    )

    with pytest.raises(PriceNotFound):
        get_token_price(
            token_address="0x3472a5a71965499acd81997a54bba8d852c6e53d",
            currency="usd",
            chain=Network.Ethereum,
            use_staging=False,
        )
