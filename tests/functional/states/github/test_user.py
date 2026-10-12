import pytest

from tests.support.github import NotFound


def test_present_invites_user(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.present(name="newuser", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"old": None, "new": "User newuser exists in the org now"}
    if testmode:
        assert "will be added" in ret.comment
        with pytest.raises(NotFound):
            fake_org.get_member("newuser")
    else:
        assert fake_org.get_member("newuser").state == "pending"

        rerun = github.present(name="newuser")
        assert rerun.result is True
        assert not rerun.changes
        assert "already been invited" in rerun.comment


def test_present_existing_member(github, testmode):
    ret = github.present(name="user1", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert "already in the org" in ret.comment


def test_present_unknown_user(github, testmode):
    ret = github.present(name="ghost", test=testmode)
    assert ret.result is False


def test_absent_removes_member(github, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github.absent(name="user2", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"old": "User user2 exists", "new": "User user2 deleted"}
    if testmode:
        assert "will be deleted" in ret.comment
        fake_org.get_member("user2")
    else:
        with pytest.raises(NotFound):
            fake_org.get_member("user2")

        rerun = github.absent(name="user2")
        assert rerun.result is True
        assert not rerun.changes


def test_absent_nonmember(github, testmode):
    ret = github.absent(name="newuser", test=testmode)
    assert ret.result is True
    assert not ret.changes


def test_absent_unknown_user(github, testmode):
    ret = github.absent(name="ghost", test=testmode)
    assert ret.result is True
    assert "does not exist" in ret.comment
