import boto3
from ethereum_kms_signer import (
    get_eth_address as get_kms_eth_address,
    sign_transaction as sign_transaction_with_kms,
)
from web3 import Web3

# note: copied from badger-rewards
def get_assume_role_credentials(assume_role_arn: str):
    sts_client = boto3.client("sts")

    # Call the assume_role method of the STSConnection object and pass the role
    # ARN and a role session name.
    assumed_role_object = sts_client.assume_role(
        RoleArn=assume_role_arn, RoleSessionName="AssumeRoleSession1"
    )

    # From the response that contains the assumed role, get the temporary
    # credentials that can be used to make subsequent API calls
    credentials = assumed_role_object["Credentials"]

    return credentials


class SignerMixin:
    """
    Mixin for signing transactions. Signs with a hot wallet or with AWS KMS
    service depending on the signing method it is initialized with.

    Can use AWS STS for interacting with KMS if specified.

    Usage:
    For using a hot wallet signer, instantiate mixin with following args:
        - keeper_key
        - keeper_address
        - signing_method = 'pk'
        - web3
    For using a KMS signer, instantiate mixin with following args:
        - keeper_kms_key_id
        - signing_method = 'kms'
        - region_name
        - assume_role_arn

    For signing transactions call `self.__sign_transaction` with the
    transaction dict.
    """

    def __init__(
        self,
        keeper_key: str = None,
        keeper_address: str = "",
        signing_method: str = "pk",
        keeper_kms_key_id: str = None,
        assume_role_arn: str = None,
        region_name: str = "us-west-1",
        web3: Web3 = None,
    ):
        self._signing_method = signing_method

        self._keeper_key = keeper_key
        self._keeper_address = keeper_address

        self._keeper_kms_key_id = keeper_kms_key_id
        self._region_name = region_name
        self._assume_role_arn = assume_role_arn

        self._kms_session = None
        self._kms_client = None
        self._keeper_kms_address = None

        self.web3 = web3

    @property
    def kms_session(self):
        if self._kms_session is None:
            if self._assume_role_arn:
                credentials = get_assume_role_credentials(self._assume_role_arn)
                self._kms_session = boto3.session.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
            else:
                self._kms_session = boto3.session.Session()
        return self._kms_session

    @property
    def kms_client(self):
        if self._kms_client is None:
            self._kms_client = self.kms_session.client(
                service_name="kms", region_name=self._region_name
            )
        return self._kms_client

    @property
    def keeper_address(self):
        if self._signing_method == "kms":
            if self._kms_keeper_address is None:
                self._kms_keeper_address = get_kms_eth_address(
                    self._keeper_kms_key_id, self.kms_client
                )

            return self._kms_keeper_address
        return self._keeper_address

    def sign_transaction(self, tx: dict):
        if self._signing_method == "kms":
            return sign_transaction_with_kms(
                tx, self._keeper_kms_key_id, self.kms_client
            )
        else:
            return self.web3.eth.account.sign_transaction(
                tx, private_key=self._keeper_key
            )
