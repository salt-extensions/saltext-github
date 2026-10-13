import pytest

from tests.support.github import NotFound


def test_member_present_invites_user(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.member_present(name="newuser", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"invited": "newuser"}
    if testmode:
        assert "would have been invited" in ret.comment
        with pytest.raises(NotFound):
            fake_org.get_member("newuser")
    else:
        assert fake_org.get_member("newuser").state == "pending"

        rerun = github_org.member_present(name="newuser")
        assert rerun.result is True
        assert not rerun.changes
        assert "already been invited" in rerun.comment


def test_member_present_existing_member(github_org, fake_github, testmode):
    ret = github_org.member_present(name="user1", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert "already a member" in ret.comment
    assert not fake_github.mutations()


def test_member_present_unknown_user(github_org, testmode):
    ret = github_org.member_present(name="ghost", test=testmode)
    assert ret.result is False
    assert "does not exist" in ret.comment


def test_member_absent_removes_member(github_org, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_org.member_absent(name="user2", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"removed": "user2"}
    if testmode:
        assert "would have been removed" in ret.comment
        fake_org.get_member("user2")
    else:
        with pytest.raises(NotFound):
            fake_org.get_member("user2")

        rerun = github_org.member_absent(name="user2")
        assert rerun.result is True
        assert not rerun.changes


def test_member_absent_nonmember(github_org, fake_github, testmode):
    ret = github_org.member_absent(name="newuser", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_member_absent_unknown_user(github_org, testmode):
    ret = github_org.member_absent(name="ghost", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert "does not exist" in ret.comment
