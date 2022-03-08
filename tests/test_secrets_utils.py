from unittest.mock import MagicMock

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
