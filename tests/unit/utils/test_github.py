from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from saltext.github.utils import github


@pytest.fixture()
def users():
    return [
        "user1",
        {
            "user2": [
                "12345",
                "67890",
            ],
        },
    ]


def test_get_user_pubkeys_not_a_list():
    # should fail, because we only want to allow a list
    users = {}
    assert github.get_user_pubkeys(users) == {"Error": "A list of users is expected"}


def test_get_user_pubkeys_empty_key_returns(users):
    mock_query = MagicMock(return_value={"text": "{}"})
    expected = {"user1": {}, "user2": {}}
    with patch("salt.utils.http.query", mock_query):
        ret = github.get_user_pubkeys(users)
    assert ret == expected


def test_get_user_pubkeys_key_returns(users):
    mock_query = MagicMock(
        side_effect=[
            {
                "text": '[{"id": 1, "key": "ssh-rsa AAA..."}]',
            },
            {
                "text": '[{"id": 12345, "key": "ssh-rsa AAA..."},{"id": 99999, "key": "ssh-ed25519 AAA..."}]',
            },
        ]
    )
    expected = {"user1": {1: "ssh-rsa AAA..."}, "user2": {12345: "ssh-rsa AAA..."}}
    with patch("salt.utils.http.query", mock_query):
        ret = github.get_user_pubkeys(users)
    assert ret == expected
