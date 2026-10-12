import pytest

from tests.support.github import NotFound


def test_team_present_create(github, fake_org):
    ret = github.team_present(
        name="team-b", description="Team B", privacy="closed", members={"user1": {}}
    )
    assert ret.result is True
    assert "team" in ret.changes
    assert "user1" in ret.changes
    created = fake_org.get_team("team-b")
    assert set(created.data.members) == {"user1"}


def test_team_present_idempotent(github):
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        permission="pull",
        members={"user1": {}},
    )
    assert ret.result is True
    assert not ret.changes


def test_team_present_converges_drift(github, fake_org):
    ret = github.team_present(
        name="Team A",
        description="Updated A",
        privacy="closed",
        permission="pull",
        members={"user2": {}},
    )
    assert ret.result is True
    assert "team" in ret.changes
    assert "user1" in ret.changes  # removed (managed members)
    assert "user2" in ret.changes  # added
    team = fake_org.get_team("team-a")
    assert team.description == "Updated A"
    assert set(team.data.members) == {"user2"}


def test_team_present_enforce_mfa(github, fake_org):
    ret = github.team_present(
        name="Team A",
        description="Awesome Team: Team A",
        privacy="closed",
        permission="pull",
        members={"user1": {}, "user2": {}},
        enforce_mfa=True,
    )
    assert ret.result is True
    # user2 has no MFA and must not be added
    assert set(fake_org.get_team("team-a").data.members) == {"user1"}


def test_team_present_test_mode(github, fake_github, fake_org):
    before = len(fake_github.mutations())
    ret = github.team_present(name="Team A", description="Else", test=True)
    assert ret.result is None
    assert "set to be edited" in ret.comment
    assert len(fake_github.mutations()) == before
    assert fake_org.get_team("team-a").description == "Awesome Team: Team A"


def test_team_absent(github, fake_org):
    fake_org.get_team("team-a")
    ret = github.team_absent(name="Team A")
    assert ret.result is True
    assert ret.changes
    with pytest.raises(NotFound):
        fake_org.get_team("team-a")

    rerun = github.team_absent(name="Team A")
    assert rerun.result is True
    assert not rerun.changes


def test_team_absent_test_mode(github, fake_github, fake_org):
    fake_org.get_team("team-a")
    before = len(fake_github.mutations())
    ret = github.team_absent(name="Team A", test=True)
    assert ret.result is None
    assert len(fake_github.mutations()) == before
    fake_org.get_team("team-a")
