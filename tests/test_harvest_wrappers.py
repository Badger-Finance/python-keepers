from unittest.mock import MagicMock

import pytest

from src.general_harvester import GeneralHarvester
from src.harvest_wrappers import safe_harvest


@pytest.fixture
def harvester(mocker) -> GeneralHarvester:
    mocker.patch(
        "src.general_harvester.get_last_harvest_times",
        return_value={},
    )
    yield GeneralHarvester(
        web3=MagicMock(),
        keeper_acl="0x",
        keeper_address="0x",
    )


def test_safe_harvest_happy(harvester):
    """
    Simple unit to check that all important harvester methods are called
    """

    harvester.harvest = MagicMock()
    harvester.harvest_no_return = MagicMock()
    harvester.tend_then_harvest = MagicMock()

    assert safe_harvest(harvester, MagicMock()) == "Success!"

    assert harvester.harvest.called
    assert not harvester.harvest_no_return.called
    assert not harvester.tend_then_harvest.called


def test_safe_harvest_fail(harvester):
    """
    Simple unit to check that if harvest() fails, harvest_no_return is called as well
    """
    harvester.harvest = MagicMock(side_effect=Exception)
    harvester.harvest_no_return = MagicMock()
    harvester.tend_then_harvest = MagicMock()

    assert safe_harvest(harvester, MagicMock()) == "Success!"

    assert harvester.harvest.called
    assert harvester.harvest_no_return.called
    assert not harvester.tend_then_harvest.called


def test_safe_harvest_fail_no_return(harvester):
    """
    Simple unit to check that if harvest() and harvest_no_return fail, tend_then_harvest()
    is called
    """
    harvester.harvest = MagicMock(side_effect=Exception)
    harvester.harvest_no_return = MagicMock(side_effect=Exception)
    harvester.tend_then_harvest = MagicMock()

    assert safe_harvest(harvester, MagicMock()) == "Success!"

    assert harvester.harvest.called
    assert harvester.harvest_no_return.called
    assert harvester.tend_then_harvest.called


def test_safe_harvest_all_fail(harvester):
    """
    Case when everything fails :(
    """
    harvester.harvest = MagicMock(side_effect=Exception)
    harvester.harvest_no_return = MagicMock(side_effect=Exception)
    harvester.tend_then_harvest = MagicMock(side_effect=Exception)
    # No success string
    assert safe_harvest(harvester, MagicMock()) is None

    assert harvester.harvest.called
    assert harvester.harvest_no_return.called
    assert harvester.tend_then_harvest.called
