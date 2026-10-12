import pytest
from salt.exceptions import CommandExecutionError


def test_list_members(github_org):
    assert sorted(github_org.list_members()) == ["user1", "user2"]


def test_list_members_uses_cache(github_org, fake_org):
    assert sorted(github_org.list_members()) == ["user1", "user2"]
    fake_org.add_member("newuser")
    # Cached result is returned until the cache is bypassed
    assert sorted(github_org.list_members()) == ["user1", "user2"]
    assert sorted(github_org.list_members(ignore_cache=True)) == ["newuser", "user1", "user2"]


def test_get_member(github_org):
    ret = github_org.get_member("user1")
    assert ret["login"] == "user1"
    assert ret["company"] == "Example Corp"
    assert ret["in_org"] is True
    assert ret["membership_state"] == "active"


def test_get_member_nonmember(github_org):
    ret = github_org.get_member("newuser")
    assert ret["in_org"] is False
    assert ret["membership_state"] == "nonexistent"


def test_get_member_unknown_user(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.get_member("ghost")


def test_add_member(github_org, fake_org):
    assert github_org.add_member("newuser") is True  # membership is pending
    assert fake_org.get_member("newuser").state == "pending"
    ret = github_org.get_member("newuser")
    assert ret["membership_state"] == "pending"
    assert ret["in_org"] is False


def test_add_member_unknown_user(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.add_member("ghost")


def test_remove_member(github_org, fake_org):
    assert github_org.remove_member("user2") is True
    assert "user2" not in [member.data.login for member in fake_org.members]
    assert sorted(github_org.list_members(ignore_cache=True)) == ["user1"]


def test_remove_member_not_a_member(github_org):
    # Idempotent: the user is not a member afterwards
    assert github_org.remove_member("newuser") is True


def test_remove_member_unknown_user(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.remove_member("ghost")


def test_list_members_without_mfa(github_org, fake_state):
    assert github_org.list_members_without_mfa() == ["user2"]
    fake_state.get_user("user1").data.two_factor_authentication = False
    # Cached result is returned until the cache is bypassed
    assert github_org.list_members_without_mfa() == ["user2"]
    assert sorted(github_org.list_members_without_mfa(ignore_cache=True)) == ["user1", "user2"]
