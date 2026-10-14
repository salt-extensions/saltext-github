import pytest
from salt.exceptions import CommandExecutionError

from tests.support.github import USER_KEY_A
from tests.support.github import USER_KEY_B


def test_list_keys(github_user):
    ret = github_user.list_keys("user1")
    assert [key["key"] for key in ret] == [USER_KEY_A, USER_KEY_B]
    assert all(isinstance(key["id"], int) for key in ret)


def test_list_keys_defaults_to_token_user(github_user):
    ret = github_user.list_keys()
    assert [key["key"] for key in ret] == [USER_KEY_A, USER_KEY_B]


def test_list_keys_none_present(github_user):
    assert github_user.list_keys("user2") == []


def test_list_keys_unknown(github_user):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_user.list_keys("ghost")
