from typing import Union

import requests


def get_token_price(
    token_address: str, currency: str, chain: str, use_staging: bool = False
) -> Union[int]:
    base_url = "https://staging-api.badger.finance" if use_staging else "https://api.badger.finance"
    response = requests.get(
        f"{base_url}/v2/prices?currency={currency}&chain={chain}"
    )
    response.raise_for_status()
    return response.json().get(token_address, 0)
