from enum import Enum


class Network(str, Enum):
    Ethereum = "ethereum"
    Polygon = "polygon"
    Arbitrum = "arbitrum"
    BinanceSmartChain = "binancesmartchain"
    Avalanche = "avalanche"
    Fantom = "fantom"
    xDai = "xdai"

    def __str__(self):
        return self.value


class Currency(str, Enum):
    Eth = "eth"
    Matic = "matic"
    Usd = "usd"
    Btc = "btc"
    Ftm = "ftm"

    def __str__(self):
        return self.value


class VaultVersion(str, Enum):
    v1_5 = "1.5"
    v1 = "1"
    v2 = "2"

    def __str__(self):
        return self.value


class DiscordRoles(Enum):
    RewardsPod = "<@&804147406043086850>"
    CriticalErrorRole = "<@&974386521148891166>"


class VaultStatus(Enum):
    Discontinued = 0
    Experimental = 1
    Guarded = 2
    Open = 3

    def __str__(self):
        return self.value
