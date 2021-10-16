# POLY
POLY_GAS_ORACLE = "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"
POLY_KEEPER_ACL = "0x46fa8817624eea8052093eab8e3fdf0e2e0443b2"
POLY_VAULT_OWNER = "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"
POLY_REGISTRY = "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f"

# ARBITRUM
ARBITRUM_GAS_ORACLE = "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612"
ARBITRUM_KEEPER_ACL = "0x265820F3779f652f2a9857133fDEAf115b87db4B"
ARBITRUM_REGISTRY = "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f"

# ETH
ETH_GAS_ORACLE = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
ETH_KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"
ETH_REGISTRY = "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f"
ETH_REWARDS_MANAGER = "0x5B60952481Eb42B66bdfFC3E049025AC5b91c127"

ETH_BDIGG_STRATEGY = "0x4a8651F2edD68850B944AD93f2c67af817F39F62"
ETH_BDIGG_VAULT = "0x7e7E112A68d8D2E221E11047a72fFC1065c38e1a"
ETH_BBADGER = "0x75b8E21BD623012Efb3b69E1B562465A68944eE6"
ETH_DIGG_SUSHI_LP_STRATEGY = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
ETH_DIGG_SUSHI_LP_VAULT = "0x88128580ACdD9c04Ce47AFcE196875747bF2A9f6"

DIGG_TOKEN = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
BADGER_TOKEN = "0x3472A5A71965499acd81997a54BBA8D852C6E53d"
WBTC_TOKEN = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

DAYS_IN_WEEK = 7

MULTICHAIN_CONFIG = {
    "poly": {
        "gas_oracle": POLY_GAS_ORACLE,
        "keeper_acl": POLY_KEEPER_ACL,
        "vault_owner": [POLY_VAULT_OWNER],
        "registry": POLY_REGISTRY,
        "earn": {"invalid_strategies": []},
    },
    "arbitrum": {
        "gas_oracle": ARBITRUM_GAS_ORACLE,
        "keeper_acl": ARBITRUM_KEEPER_ACL,
        "vault_owner": [
            "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556",
            "0xbb2281ca5b4d07263112604d1f182ad0ab26a252",
            "0x283c857ba940a61828d9f4c09e3fcee2e7aef3f7",
        ],
        "registry": ARBITRUM_REGISTRY,
        "earn": {"invalid_strategies": []},
        "harvest": {"invalid_strategies": []},
    },
    "eth": {
        "gas_oracle": ETH_GAS_ORACLE,
        "keeper_acl": ETH_KEEPER_ACL,
        "vault_owner": ["0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"],
        "registry": ETH_REGISTRY,
        "rewards_manager": ETH_REWARDS_MANAGER,
        "earn": {"invalid_strategies": ["0x3ff634ce65cDb8CC0D569D6d1697c41aa666cEA9"]},
        "external_harvest": {
            "single_asset": {
                "strategies": [
                    ETH_BDIGG_STRATEGY,  # bdigg
                    ETH_BBADGER,  # bbadger
                ]
            },
            "liquidity_pool": {
                "strategies": [
                    ETH_DIGG_SUSHI_LP_STRATEGY,
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
