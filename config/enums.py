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
