import base64
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from config.enums import Network
from src.utils import NoHealthyNode
from src.utils import get_healthy_node
from src.utils import get_node_url
from src.aws import get_secret


def test_get_secret_happy(mocker):
    secret_string = '{"some_key": "secret_value"}'
    mocker.patch(
        "src.aws.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        return_value={
                            "SecretString": secret_string,
                        }
                    )
                )
            )
        ),
    )
    assert get_secret("some_secret_name", "some_key") == "secret_value"


def test_get_secret_happy_binary(mocker):
    binary_secret_string = '{"some_key": "secret_value"}'
    string_bytes = binary_secret_string.encode("ascii")
    mocker.patch(
        "src.aws.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        return_value={
                            "SecretBinary": base64.b64encode(string_bytes),
                        }
                    )
                )
            )
        ),
    )
    assert get_secret("some_secret_name", "some_key") == "secret_value"


def test_get_secret_client_raises(mocker):
    mocker.patch(
        "src.aws.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        side_effect=ClientError(
                            {"Error": {"Code": "DecryptionFailureException"}}, ""
                        )
                    )
                )
            )
        ),
    )
    with pytest.raises(ClientError):
        get_secret("some_secret_name", "some_key")


@pytest.mark.parametrize("chain", [Network.Ethereum, Network.Polygon, Network.Fantom])
def test_get_node_url(chain, mocker):
    secret_string = '{"NODE_URL": "secret_value"}'
    mocker.patch(
        "src.aws.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        return_value={
                            "SecretString": secret_string,
                        }
                    )
                )
            )
        ),
    )
    assert get_node_url(chain) == "secret_value"


@pytest.mark.parametrize("chain", [Network.Ethereum, Network.Polygon, Network.Fantom])
def test_get_healthy_node(chain, mocker):
    secret_string = '{"NODE_URL": "secret_value"}'
    mocker.patch(
        "src.aws.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        return_value={
                            "SecretString": secret_string,
                        }
                    )
                )
            )
        ),
    )
    web3_mock = mocker.patch(
        'src.utils.Web3',
        return_value=MagicMock(
            eth=MagicMock(get_block_number=MagicMock(return_value={}))
        )
    )
    assert get_healthy_node(chain) is not None
    assert web3_mock.return_value.eth.get_block_number.called


@pytest.mark.parametrize("chain", [Network.Ethereum, Network.Polygon, Network.Fantom])
def test_get_healthy_node_no_healthy_node(chain, mocker):
    secret_string = '{"NODE_URL": "secret_value"}'
    mocker.patch(
        "src.aws.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        return_value={
                            "SecretString": secret_string,
                        }
                    )
                )
            )
        ),
    )
    mocker.patch(
        'src.utils.Web3',
        return_value=MagicMock(
            eth=MagicMock(get_block_number=MagicMock(side_effect=ValueError))
        )
    )
    with pytest.raises(NoHealthyNode):
        get_healthy_node(chain)
