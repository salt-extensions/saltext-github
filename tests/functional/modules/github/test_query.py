import pytest
from salt.exceptions import CommandExecutionError


def test_query_single_object(github):
    ret = github.query("users/user2")
    assert ret["login"] == "user2"


def test_query_accepts_leading_slash(github):
    assert github.query("/users/user2")["login"] == "user2"


def test_query_accepts_path_segments(github):
    assert github.query(["users", "user2"])["login"] == "user2"


def test_query_merges_pages(github):
    ret = github.query("orgs/testorg/members", per_page=1)
    assert sorted(user["login"] for user in ret) == ["user1", "user2"]


def test_query_params(github):
    ret = github.query("orgs/testorg/members", params={"filter": "2fa_disabled"})
    assert sorted(user["login"] for user in ret) == ["user2"]


def test_query_method_and_data(github, fake_org):
    ret = github.query("repos/testorg/repo-a/labels", method="POST", data='{"name": "new-label"}')
    assert ret["name"] == "new-label"
    assert "new-label" in fake_org.get_repo("repo-a").labels


def test_query_not_found(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.query("users/ghost")
