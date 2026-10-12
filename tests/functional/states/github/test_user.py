import pytest

from tests.support.github import NotFound


def test_present_invites_user(github, fake_org):
    ret = github.present(name="newuser")
    assert ret.result is True
    assert ret.changes
    assert fake_org.get_member("newuser").state == "pending"

    rerun = github.present(name="newuser")
    assert rerun.result is True
    assert not rerun.changes
    assert "already been invited" in rerun.comment


def test_present_existing_member(github):
    ret = github.present(name="user1")
    assert ret.result is True
    assert not ret.changes
    assert "already in the org" in ret.comment


def test_present_unknown_user(github):
    ret = github.present(name="ghost")
    assert ret.result is False


def test_present_test_mode(github, fake_github, fake_org):
    before = len(fake_github.mutations())
    ret = github.present(name="newuser", test=True)
    assert ret.result is None
    assert "will be added" in ret.comment
    assert len(fake_github.mutations()) == before
    with pytest.raises(NotFound):
        fake_org.get_member("newuser")


def test_absent_removes_member(github, fake_org):
    ret = github.absent(name="user2")
    assert ret.result is True
    with pytest.raises(NotFound):
        fake_org.get_member("user2")

    rerun = github.absent(name="user2")
    assert rerun.result is True
    assert not rerun.changes


def test_absent_nonmember(github):
    ret = github.absent(name="newuser")
    assert ret.result is True
    assert not ret.changes


def test_absent_test_mode(github, fake_github, fake_org):
    before = len(fake_github.mutations())
    ret = github.absent(name="user1", test=True)
    assert ret.result is None
    assert len(fake_github.mutations()) == before
    fake_org.get_member("user1")
