import pytest

from tests.support.github import NotFound


@pytest.fixture
def _instant_sleep(monkeypatch):
    # repo_present waits for repo creation to settle; pointless against the fake
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


def test_repo_present_create(github, fake_org, _instant_sleep):
    ret = github.repo_present(name="new-repo", description="Fancy")
    assert ret.result is True
    assert "repo" in ret.changes
    assert fake_org.get_repo("new-repo").description == "Fancy"


def test_repo_present_idempotent(github):
    ret = github.repo_present(name="repo-a", description="Test repo repo-a")
    assert ret.result is True
    assert not ret.changes


def test_repo_present_converges_drift(github, fake_org):
    ret = github.repo_present(name="repo-a", description="Managed description")
    assert ret.result is True
    assert "repo" in ret.changes
    assert fake_org.get_repo("repo-a").description == "Managed description"

    rerun = github.repo_present(name="repo-a", description="Managed description")
    assert rerun.result is True
    assert not rerun.changes


def test_repo_present_test_mode(github, fake_github, fake_org):
    before = len(fake_github.mutations())
    ret = github.repo_present(name="ghost-repo", description="Would be", test=True)
    assert ret.result is None
    assert ret.changes
    assert len(fake_github.mutations()) == before
    with pytest.raises(NotFound):
        fake_org.get_repo("ghost-repo")


def test_repo_present_manages_teams(github, fake_org):
    ret = github.repo_present(name="repo-a", teams={"Team A": "push"})
    assert ret.result is True
    assert "Team A" in ret.changes
    team_a = fake_org.get_team("team-a")
    assert team_a.repos["repo-a"] == "push"

    # An empty teams dict removes the repo from unlisted teams
    removal = github.repo_present(name="repo-a", teams={})
    assert removal.result is True
    assert "Team A" in removal.changes
    assert "repo-a" not in fake_org.get_team("team-a").repos


def test_repo_absent(github, fake_org):
    ret = github.repo_absent(name="repo-a")
    assert ret.result is True
    assert ret.changes
    with pytest.raises(NotFound):
        fake_org.get_repo("repo-a")

    rerun = github.repo_absent(name="repo-a")
    assert rerun.result is True
    assert not rerun.changes


def test_repo_absent_test_mode(github, fake_github, fake_org):
    before = len(fake_github.mutations())
    ret = github.repo_absent(name="repo-b", test=True)
    assert ret.result is None
    assert len(fake_github.mutations()) == before
    fake_org.get_repo("repo-b")
