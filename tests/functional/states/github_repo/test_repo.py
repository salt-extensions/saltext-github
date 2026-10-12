import pytest

from tests.support.github import NotFound


@pytest.fixture
def _instant_sleep(monkeypatch):
    # present waits for repo creation to settle; pointless against the fake
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


def test_present_create(github_repo, fake_github, fake_org, _instant_sleep, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present(name="new-repo", description="Fancy", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "repo" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    if testmode:
        with pytest.raises(NotFound):
            fake_org.get_repo("new-repo")
    else:
        assert fake_org.get_repo("new-repo").description == "Fancy"


def test_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.present(name="repo-a", description="Test repo repo-a", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_present_converges_drift(github_repo, fake_org, testmode):
    ret = github_repo.present(name="repo-a", description="Managed description", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "repo" in ret.changes
    expected = "Test repo repo-a" if testmode else "Managed description"
    assert fake_org.get_repo("repo-a").description == expected
    if not testmode:
        rerun = github_repo.present(name="repo-a", description="Managed description")
        assert rerun.result is True
        assert not rerun.changes


def test_present_default_branch(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present(name="repo-a", default_branch="develop", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "repo" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "main" if testmode else "develop"
    assert fake_org.get_repo("repo-a").default_branch == expected


def test_present_default_branch_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.present(name="repo-a", default_branch="main", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_present_create_ignores_default_branch(github_repo, fake_org, _instant_sleep, testmode):
    # The default branch can only be switched to an existing branch,
    # so it is not applied on repository creation
    ret = github_repo.present(name="new-repo", default_branch="develop", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "repo" in ret.changes
    if not testmode:
        assert fake_org.get_repo("new-repo").default_branch == "main"


def test_present_create_with_teams(github_repo, fake_github, fake_org, _instant_sleep, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present(name="new-repo", teams={"Team A": "push"}, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "repo" in ret.changes
    assert "Team A" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    if testmode:
        assert "new-repo" not in fake_org.repos
    else:
        assert fake_org.get_team("team-a").repos["new-repo"] == "push"


def test_present_adds_repo_to_team(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present(name="repo-b", teams={"Team A": "push"}, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "Team A" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    team = fake_org.get_team("team-a")
    if testmode:
        assert "repo-b" not in team.repos
    else:
        assert team.repos["repo-b"] == "push"


def test_present_team_permission_change(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.present(name="repo-a", teams={"Team A": "push"}, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "Team A" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "pull" if testmode else "push"
    assert fake_org.get_team("team-a").repos["repo-a"] == expected


def test_present_team_permission_unchanged(github_repo, fake_github, fake_org, testmode):
    ret = github_repo.present(name="repo-a", teams={"Team A": "pull"}, test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
    assert fake_org.get_team("team-a").repos["repo-a"] == "pull"


def test_present_team_removal(github_repo, fake_github, fake_org, testmode):
    # An empty teams dict removes the repo from unlisted teams
    before = len(fake_github.mutations())
    ret = github_repo.present(name="repo-a", teams={}, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "Team A" in ret.changes
    assert (len(fake_github.mutations()) == before) is testmode
    assert ("repo-a" in fake_org.get_team("team-a").repos) is testmode


def test_present_missing_team(github_repo):
    ret = github_repo.present(name="repo-b", teams={"Ghost": "pull"})
    assert ret.result is False
    assert "Failed" in ret.comment


def test_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.absent(name="repo-a", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (len(fake_github.mutations()) == before) is testmode
    assert ret.changes == {"old": "Repo repo-a exists", "new": "Repo repo-a deleted"}
    if testmode:
        assert "would have been deleted" in ret.comment
        fake_org.get_repo("repo-a")
    else:
        with pytest.raises(NotFound):
            fake_org.get_repo("repo-a")

        rerun = github_repo.absent(name="repo-a")
        assert rerun.result is True
        assert not rerun.changes
