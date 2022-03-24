from unittest.mock import MagicMock

import pytest

from config.enums import Network
from src.general_harvester import GeneralHarvester
from src.misc_utils import hours


@pytest.mark.parametrize(
    "chain",
    [Network.Ethereum, Network.Fantom]
)
def test_time_to_harvest_true(mocker, chain: Network):
    strategy = "0x123123"
    time_now = 1648111656
    harvest_timestamp = time_now - hours(97)
    mocker.patch(
        "src.general_harvester.get_last_harvest_times",
        # Some strategy with timestamp in the past
        return_value={
            strategy: harvest_timestamp,
        },
    )
    # Last harvest happened more than 96 hours ago, so it's time to harvest again
    harvester = GeneralHarvester(
        chain=chain,
        web3=MagicMock(
            eth=MagicMock(
                get_block=MagicMock(
                    return_value={'timestamp': time_now}
                )
            )
        ),
        keeper_acl="0x",
        keeper_address="0x",
    )
    assert harvester.is_time_to_harvest(MagicMock(address=strategy), hours(96))


@pytest.mark.parametrize(
    "chain",
    [Network.Ethereum, Network.Fantom]
)
def test_time_to_harvest_false(mocker, chain: Network):
    """
    Not enough time passed since last harvest, so not time to run it
    """
    strategy = "0x123123"
    time_now = 1648111656
    harvest_timestamp = time_now - hours(95)
    mocker.patch(
        "src.general_harvester.get_last_harvest_times",
        return_value={
            strategy: harvest_timestamp,
        },
    )
    harvester = GeneralHarvester(
        chain=chain,
        web3=MagicMock(
            eth=MagicMock(
                get_block=MagicMock(
                    return_value={'timestamp': time_now}
                )
            )
        ),
        keeper_acl="0x",
        keeper_address="0x",
    )
    assert harvester.is_time_to_harvest(MagicMock(address=strategy), hours(96)) is False
