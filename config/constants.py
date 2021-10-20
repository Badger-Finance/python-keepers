ETH_BVECVX_STRATEGY = "0x3ff634ce65cDb8CC0D569D6d1697c41aa666cEA9"
ETH_RETIRED_CVX_STRATEGY = "0x87fB47c2B9EB41d362BAb44F5Ec81514b6b1de13"
ETH_TRICRYPTO_STRATEGY = "0x05eC4356e1acd89CC2d16adC7415c8c95E736AC1"
ETH_HARVEST_STRATEGY = "0xaaE82E3c89e15E6F26F60724f115d5012363e030"
ETH_UNI_DIGG_STRATEGY = "0xadc8d7322f2E284c1d9254170dbe311E9D3356cf"
ETH_BBADGER_STRATEGY = "0x75b8E21BD623012Efb3b69E1B562465A68944eE6"
ETH_YVWBTC_VAULT = "0x4b92d19c11435614CD49Af1b589001b7c08cD4D5"

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
        "earn": {"invalid_strategies": ["0x85386C3cE0679b035a9F8F17f531C076d0b35954"]},
        "harvest": {"invalid_strategies": []},
    },
    "eth": {
        "gas_oracle": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "keeper_acl": "0x711A339c002386f9db409cA55b6A35a604aB6cF6",
        "vault_owner": ["0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "rewards_manager": "0x5B60952481Eb42B66bdfFC3E049025AC5b91c127",
        "earn": {
            "invalid_strategies": [
                ETH_BVECVX_STRATEGY,
                ETH_RETIRED_CVX_STRATEGY,
                ETH_TRICRYPTO_STRATEGY,
                ETH_HARVEST_STRATEGY,
                ETH_UNI_DIGG_STRATEGY,
                ETH_BBADGER_STRATEGY,
            ]
        },
    },
}

EARN_PCT_THRESHOLD = 0.01
EARN_OVERRIDE_THRESHOLD = 2
THREE_DAYS_OF_BLOCKS = 21_000
