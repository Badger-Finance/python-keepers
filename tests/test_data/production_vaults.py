PRODUCTION_VAULT_RAW = (
    (
        "v1",
        0,
        (
            (
                "0xd04c48A53c111300aD41190D63681ed3dAd998eC",
                "name=renBTC/wBTC/sBTC,protocol=Convex,behavior=None",
            ),
            (
                "0xb9D076fDe463dbc9f915E5392F807315Bf940334",
                "name=tBTC/sBTC,protocol=Convex,behavior=None",
            ),
            (
                "0xAf5A1DECfa95BAF63E0084a35c62592B774A2A87",
                "name=renBTC/wBTC,protocol=Curve,behavior=None",
            ),
            (
                "0x235c9e24D3FB2FAFd58a2E49D454Fdcd2DBf7FF1",
                "name=wBTC/Badger,protocol=Uniswap,behavior=None",
            ),
            (
                "0xC17078FDd324CC473F8175Dc5290fae5f2E84714",
                "name=wBTC/Digg,protocol=Uniswap,behavior=None",
            ),
            (
                "0x19D97D8fA813EE2f51aD4B4e04EA08bAf4DFfC28",
                "name=Badger,protocol=Badger,behavior=None",
            ),
            (
                "0x8a8FFec8f4A0C8c9585Da95D9D97e8Cd6de273DE",
                "name=wBTC/ibBTC,protocol=Sushiswap,behavior=None",
            ),
            (
                "0x8c76970747afd5398e958bDfadA4cf0B9FcA16c4",
                "name=hBTC,protocol=Convex,behavior=None",
            ),
            (
                "0x55912D0Cf83B75c492E761932ABc4DB4a5CB1b17",
                "name=pBTC,protocol=Convex,behavior=None",
            ),
            (
                "0xf349c0faA80fC1870306Ac093f75934078e28991",
                "name=oBTC,protocol=Convex,behavior=None",
            ),
            (
                "0x5Dce29e92b1b939F8E8C60DcF15BDE82A85be4a9",
                "name=bBTC,protocol=Convex,behavior=None",
            ),
            (
                "0xBE08Ef12e4a553666291E9fFC24fCCFd354F2Dd2",
                "name=Tricrypto,protocol=Convex,behavior=None",
            ),
            (
                "0x53C8E199eb2Cb7c01543C137078a038937a68E40",
                "name=CVX,protocol=Convex,behavior=None",
            ),
            (
                "0x599D92B453C010b1050d31C364f6ee17E819f193",
                "name=imBTC,protocol=mStable,behavior=None",
            ),
            (
                "0x26B8efa69603537AC8ab55768b6740b67664D518",
                "name=mhBTC,protocol=mStable,behavior=None",
            ),
            (
                "0x19E4d89e0cB807ea21B8CEF02df5eAA99A110dA5",
                "name=MIM/3CRV,protocol=Convex,behavior=None",
            ),
            (
                "0x15cBC4ac1e81c97667780fE6DAdeDd04a6EEB47B",
                "name=FRAX/3CRV,protocol=Convex,behavior=None",
            ),
        ),
    ),
    ("v1", 1, ()),
    ("v1", 2, ()),
    (
        "v1",
        3,
        (
            (
                "0x6dEf55d2e18486B9dDfaA075bc4e4EE0B28c1545",
                "name=renBTC/wBTC,protocol=Convex,behavior=None",
            ),
            (
                "0x758A43EE2BFf8230eeb784879CdcFF4828F2544D",
                "name=wBTC/wETH,protocol=Sushiswap,behavior=None",
            ),
            (
                "0x1862A18181346EBd9EdAf800804f89190DeF24a5",
                "name=wBTC/Badger,protocol=Sushiswap,behavior=None",
            ),
            (
                "0x88128580ACdD9c04Ce47AFcE196875747bF2A9f6",
                "name=wBTC/Digg,protocol=Sushiswap,behavior=None",
            ),
            (
                "0x7e7E112A68d8D2E221E11047a72fFC1065c38e1a",
                "name=Digg,protocol=Badger,behavior=None",
            ),
            (
                "0x4b92d19c11435614CD49Af1b589001b7c08cD4D5",
                "name=wBTC,protocol=Yearn,behavior=None",
            ),
            (
                "0x2B5455aac8d64C14786c3a29858E43b5945819C0",
                "name=cvxCRV,protocol=Convex,behavior=Ecosystem Helper",
            ),
            (
                "0x27E98fC7d05f54E544d16F58C194C2D7ba71e3B5",
                "name=Tricrypto2,protocol=Convex,behavior=None",
            ),
            (
                "0xfd05D3C7fe2924020620A8bE4961bBaA747e6305",
                "name=bveCVX,protocol=Convex,behavior=None",
            ),
            (
                "0x937B8E917d0F36eDEBBA8E459C5FB16F3b315551",
                "name=CVX/bveCVX,protocol=Curve,behavior=None",
            ),
            (
                "0xaE96fF08771a109dc6650a1BdCa62F2d558E40af",
                "name=ibBTC/crvsBTC,protocol=Convex,behavior=None",
            ),
            (
                "0x6aF7377b5009d7d154F36FE9e235aE1DA27Aea22",
                "name=remBadger,protocol=Badger,behavior=None",
            ),
            (
                "0xeC1c717A3b02582A4Aa2275260C583095536b613",
                "name=BADGER/WBTC,protocol=Convex,behavior=None",
            ),
        ),
    ),
    ("v1.5", 0, ()),
    ("v1.5", 1, ()),
    ("v1.5", 2, ()),
    ("v1.5", 3, ()),
    ("v2", 0, ()),
    ("v2", 1, ()),
    ("v2", 2, ()),
    ("v2", 3, ()),
)

PRODUCTION_VAULT_FORMATTED = {
    "1": {
        "Discontinued": {
            "0xd04c48A53c111300aD41190D63681ed3dAd998eC": {
                "name": "renBTC/wBTC/sBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0xb9D076fDe463dbc9f915E5392F807315Bf940334": {
                "name": "tBTC/sBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0xAf5A1DECfa95BAF63E0084a35c62592B774A2A87": {
                "name": "renBTC/wBTC",
                "protocol": "Curve",
                "behavior": "None",
            },
            "0x235c9e24D3FB2FAFd58a2E49D454Fdcd2DBf7FF1": {
                "name": "wBTC/Badger",
                "protocol": "Uniswap",
                "behavior": "None",
            },
            "0xC17078FDd324CC473F8175Dc5290fae5f2E84714": {
                "name": "wBTC/Digg",
                "protocol": "Uniswap",
                "behavior": "None",
            },
            "0x19D97D8fA813EE2f51aD4B4e04EA08bAf4DFfC28": {
                "name": "Badger",
                "protocol": "Badger",
                "behavior": "None",
            },
            "0x8a8FFec8f4A0C8c9585Da95D9D97e8Cd6de273DE": {
                "name": "wBTC/ibBTC",
                "protocol": "Sushiswap",
                "behavior": "None",
            },
            "0x8c76970747afd5398e958bDfadA4cf0B9FcA16c4": {
                "name": "hBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x55912D0Cf83B75c492E761932ABc4DB4a5CB1b17": {
                "name": "pBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0xf349c0faA80fC1870306Ac093f75934078e28991": {
                "name": "oBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x5Dce29e92b1b939F8E8C60DcF15BDE82A85be4a9": {
                "name": "bBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0xBE08Ef12e4a553666291E9fFC24fCCFd354F2Dd2": {
                "name": "Tricrypto",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x53C8E199eb2Cb7c01543C137078a038937a68E40": {
                "name": "CVX",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x599D92B453C010b1050d31C364f6ee17E819f193": {
                "name": "imBTC",
                "protocol": "mStable",
                "behavior": "None",
            },
            "0x26B8efa69603537AC8ab55768b6740b67664D518": {
                "name": "mhBTC",
                "protocol": "mStable",
                "behavior": "None",
            },
            "0x19E4d89e0cB807ea21B8CEF02df5eAA99A110dA5": {
                "name": "MIM/3CRV",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x15cBC4ac1e81c97667780fE6DAdeDd04a6EEB47B": {
                "name": "FRAX/3CRV",
                "protocol": "Convex",
                "behavior": "None",
            },
        },
        "Experimental": {},
        "Guarded": {},
        "Open": {
            "0x6dEf55d2e18486B9dDfaA075bc4e4EE0B28c1545": {
                "name": "renBTC/wBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x758A43EE2BFf8230eeb784879CdcFF4828F2544D": {
                "name": "wBTC/wETH",
                "protocol": "Sushiswap",
                "behavior": "None",
            },
            "0x1862A18181346EBd9EdAf800804f89190DeF24a5": {
                "name": "wBTC/Badger",
                "protocol": "Sushiswap",
                "behavior": "None",
            },
            "0x88128580ACdD9c04Ce47AFcE196875747bF2A9f6": {
                "name": "wBTC/Digg",
                "protocol": "Sushiswap",
                "behavior": "None",
            },
            "0x7e7E112A68d8D2E221E11047a72fFC1065c38e1a": {
                "name": "Digg",
                "protocol": "Badger",
                "behavior": "None",
            },
            "0x4b92d19c11435614CD49Af1b589001b7c08cD4D5": {
                "name": "wBTC",
                "protocol": "Yearn",
                "behavior": "None",
            },
            "0x2B5455aac8d64C14786c3a29858E43b5945819C0": {
                "name": "cvxCRV",
                "protocol": "Convex",
                "behavior": "Ecosystem Helper",
            },
            "0x27E98fC7d05f54E544d16F58C194C2D7ba71e3B5": {
                "name": "Tricrypto2",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0xfd05D3C7fe2924020620A8bE4961bBaA747e6305": {
                "name": "bveCVX",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x937B8E917d0F36eDEBBA8E459C5FB16F3b315551": {
                "name": "CVX/bveCVX",
                "protocol": "Curve",
                "behavior": "None",
            },
            "0xaE96fF08771a109dc6650a1BdCa62F2d558E40af": {
                "name": "ibBTC/crvsBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
            "0x6aF7377b5009d7d154F36FE9e235aE1DA27Aea22": {
                "name": "remBadger",
                "protocol": "Badger",
                "behavior": "None",
            },
            "0xeC1c717A3b02582A4Aa2275260C583095536b613": {
                "name": "BADGER/WBTC",
                "protocol": "Convex",
                "behavior": "None",
            },
        },
    },
    "1.5": {"Discontinued": {}, "Experimental": {}, "Guarded": {}, "Open": {}},
    "2": {"Discontinued": {}, "Experimental": {}, "Guarded": {}, "Open": {}},
}

PRODUCTION_VAULT_FINAL = {
    "1": {
        "0x6dEf55d2e18486B9dDfaA075bc4e4EE0B28c1545": {
            "name": "renBTC/wBTC",
            "protocol": "Convex",
            "behavior": "None",
        },
        "0x758A43EE2BFf8230eeb784879CdcFF4828F2544D": {
            "name": "wBTC/wETH",
            "protocol": "Sushiswap",
            "behavior": "None",
        },
        "0x1862A18181346EBd9EdAf800804f89190DeF24a5": {
            "name": "wBTC/Badger",
            "protocol": "Sushiswap",
            "behavior": "None",
        },
        "0x88128580ACdD9c04Ce47AFcE196875747bF2A9f6": {
            "name": "wBTC/Digg",
            "protocol": "Sushiswap",
            "behavior": "None",
        },
        "0x7e7E112A68d8D2E221E11047a72fFC1065c38e1a": {
            "name": "Digg",
            "protocol": "Badger",
            "behavior": "None",
        },
        "0x4b92d19c11435614CD49Af1b589001b7c08cD4D5": {
            "name": "wBTC",
            "protocol": "Yearn",
            "behavior": "None",
        },
        "0x2B5455aac8d64C14786c3a29858E43b5945819C0": {
            "name": "cvxCRV",
            "protocol": "Convex",
            "behavior": "Ecosystem Helper",
        },
        "0x27E98fC7d05f54E544d16F58C194C2D7ba71e3B5": {
            "name": "Tricrypto2",
            "protocol": "Convex",
            "behavior": "None",
        },
        "0xfd05D3C7fe2924020620A8bE4961bBaA747e6305": {
            "name": "bveCVX",
            "protocol": "Convex",
            "behavior": "None",
        },
        "0x937B8E917d0F36eDEBBA8E459C5FB16F3b315551": {
            "name": "CVX/bveCVX",
            "protocol": "Curve",
            "behavior": "None",
        },
        "0xaE96fF08771a109dc6650a1BdCa62F2d558E40af": {
            "name": "ibBTC/crvsBTC",
            "protocol": "Convex",
            "behavior": "None",
        },
        "0x6aF7377b5009d7d154F36FE9e235aE1DA27Aea22": {
            "name": "remBadger",
            "protocol": "Badger",
            "behavior": "None",
        },
        "0xeC1c717A3b02582A4Aa2275260C583095536b613": {
            "name": "BADGER/WBTC",
            "protocol": "Convex",
            "behavior": "None",
        },
    },
    "1.5": {},
    "2": {},
}
