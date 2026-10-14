import pytest
from salt.exceptions import CommandExecutionError


@pytest.fixture(scope="module")
def minion_config_defaults(github_profile):
    user_owner = {key: val for key, val in github_profile.items() if key != "org_name"}
    user_owner["owner"] = "user2"
    return {
        "github": github_profile,
        "github_userowner": user_owner,
    }


def test_account_info_user(github):
    ret = github.account_info("user2")
    assert ret["login"] == "user2"
    assert ret["type"] == "User"


def test_account_info_org(github):
    ret = github.account_info("otherorg")
    assert ret["login"] == "otherorg"
    assert ret["type"] == "Organization"


def test_account_info_defaults_to_owner(github):
    ret = github.account_info()
    assert ret["login"] == "testorg"
    assert ret["type"] == "Organization"


def test_account_info_defaults_to_owner_user_account(github):
    # The owner default applies even when the owner is a plain user
    # account that is not the token's user
    assert github.account_info(profile="github_userowner")["login"] == "user2"


def test_account_info_unknown(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.account_info("ghost")
