import pytest
from salt.exceptions import CommandExecutionError


def test_info(github_org):
    ret = github_org.info("otherorg")
    assert ret["login"] == "otherorg"
    assert ret["type"] == "Organization"


def test_info_defaults_to_owner(github_org):
    assert github_org.info()["login"] == "testorg"


def test_info_user_fails(github_org):
    with pytest.raises(CommandExecutionError, match="user2 is not of type Organization"):
        github_org.info("user2")


def test_info_unknown(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.info("ghost")
