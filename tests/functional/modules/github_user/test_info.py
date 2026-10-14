import pytest
from salt.exceptions import CommandExecutionError


def test_info(github_user):
    ret = github_user.info("user2")
    assert ret["login"] == "user2"
    assert ret["type"] == "User"
    assert ret["company"] == "Example Corp"
    # Organization membership is not part of the generic account lookup
    assert "in_org" not in ret
    assert "membership_state" not in ret


def test_info_defaults_to_token_user(github_user):
    assert github_user.info()["login"] == "user1"


def test_info_org_fails(github_user):
    with pytest.raises(CommandExecutionError, match="testorg is not of type User"):
        github_user.info("testorg")


def test_info_unknown(github_user):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_user.info("ghost")
