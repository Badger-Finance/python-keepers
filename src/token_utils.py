from typing import Union

import requests


class PriceNotFound(Exception):
    pass


def get_token_price(
    token_address: str, currency: str, chain: str, use_staging: bool = False
) -> Union[int]:
    staging_base_url = "https://staging-api.badger.com"
    base_url = staging_base_url if use_staging else "https://api.badger.com"

    response = requests.get(f"{base_url}/v2/prices?currency={currency}&chain={chain}")
    response.raise_for_status()
    price = response.json().get(token_address, 0)

    if price == 0:
        response = requests.get(
            f"{staging_base_url}/v2/prices?currency={currency}&chain={chain}"
        )
        response.raise_for_status()
        try:
            price = response.json()[token_address]
        except KeyError:
            raise PriceNotFound(
                f"Could not find price on prod or staging api for {token_address}"
            )

    return price
