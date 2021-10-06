MULTICHAIN_CONFIG = {
    "poly": {
        "gas_oracle": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0",
        "keeper_acl": "0x46fa8817624eea8052093eab8e3fdf0e2e0443b2",
        "vault_owner": ["0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "earn": {"invalid_strategies": []},
    },
    "arbitrum": {
        "gas_oracle": "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612",
        "keeper_acl": "0x265820F3779f652f2a9857133fDEAf115b87db4B",
        "vault_owner": [
            "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556",
            "0xbb2281ca5b4d07263112604d1f182ad0ab26a252",
            "0x283c857ba940a61828d9f4c09e3fcee2e7aef3f7",
        ],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "earn": {"invalid_strategies": []},
        "harvest": {"invalid_strategies": []},
    },
    "eth": {
        "gas_oracle": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "keeper_acl": "0x711A339c002386f9db409cA55b6A35a604aB6cF6",
        "vault_owner": ["0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "rewards_manager": "0x5B60952481Eb42B66bdfFC3E049025AC5b91c127",
        "earn": {"invalid_strategies": ["0x3ff634ce65cDb8CC0D569D6d1697c41aa666cEA9"]},
        "external_harvest": {
            "single_asset": {
                "strategies": [
                    "0x4a8651F2edD68850B944AD93f2c67af817F39F62",  # bdigg
                    "0x75b8E21BD623012Efb3b69E1B562465A68944eE6",  # bbadger
                ]
            },
            "liquidity_pool": {
                "strategies": [
                    "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a",  # digg / wbtc sushi
                    "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1",  # badger / wbtc sushi
                    "0x95826C65EB1f2d2F0EDBb7EcB176563B61C60bBf",  # badger / wbtc uni
                ]
            },
            "invalid_strategies": [
                "0xadc8d7322f2E284c1d9254170dbe311E9D3356cf"  # digg / wbtc uni
            ],
        },
    },
}

EARN_PCT_THRESHOLD = 0.01
EARN_OVERRIDE_THRESHOLD = 2
THREE_DAYS_OF_BLOCKS = 21_000
