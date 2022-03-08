import base64
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.utils import get_secret


def test_get_secret_happy(mocker):
    secret_string = '{"some_key": "secret_value"}'
    mocker.patch(
        "src.utils.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(return_value={
                        "SecretString": secret_string,
                    })
                )
            )
        )
    )
    assert get_secret("some_secret_name", "some_key") == "secret_value"


def test_get_secret_happy_binary(mocker):
    binary_secret_string = '{"some_key": "secret_value"}'
    string_bytes = binary_secret_string.encode("ascii")
    mocker.patch(
        "src.utils.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(return_value={
                        "SecretBinary": base64.b64encode(string_bytes),
                    })
                )
            )
        )
    )
    assert get_secret("some_secret_name", "some_key") == "secret_value"


def test_get_secret_client_raises(mocker):
    mocker.patch(
        "src.utils.boto3.session.Session",
        return_value=MagicMock(
            client=MagicMock(
                return_value=MagicMock(
                    get_secret_value=MagicMock(
                        side_effect=ClientError(
                            {'Error': {
                                'Code': "DecryptionFailureException"
                            }}, ''
                        )
                    )
                )
            )
        )
    )
    with pytest.raises(ClientError):
        get_secret("some_secret_name", "some_key")
