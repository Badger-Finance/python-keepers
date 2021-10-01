MULTICHAIN_CONFIG = {
    "poly": {
        "gas_oracle": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0",
        "keeper_acl": "0x46fa8817624eea8052093eab8e3fdf0e2e0443b2",
        # TODO: may need to make vault owner a list eventually
        "vault_owner": ["0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "earn": {"invalid_strategies": []},
    },
    "arbitrum": {
        "gas_oracle": "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612",
        "keeper_acl": "0x265820F3779f652f2a9857133fDEAf115b87db4B",
        # TODO: may need to make vault owner a list eventually
        "vault_owner": [
            "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556",
            "0xbb2281ca5b4d07263112604d1f182ad0ab26a252",
        ],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "earn": {"invalid_strategies": []},
    },
    "eth": {
        "gas_oracle": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "keeper_acl": "0x711A339c002386f9db409cA55b6A35a604aB6cF6",
        "vault_owner": ["0xeE8b29AA52dD5fF2559da2C50b1887ADee257556"],
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
        "earn": {"invalid_strategies": ["0x3ff634ce65cDb8CC0D569D6d1697c41aa666cEA9"]},
    },
}

EARN_PCT_THRESHOLD = 0.01
EARN_OVERRIDE_THRESHOLD = 2
