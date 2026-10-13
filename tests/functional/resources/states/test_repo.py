import pytest


def test_managed_update(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["repo.managed"]("manage repo settings", description="Managed by Salt")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["name"] == "manage repo settings"
    assert ret["changes"]["new"] == {"description": "Managed by Salt"}
    assert (len(fake_github.mutations()) == before) is testmode
    expected = "Test repo repo-a" if testmode else "Managed by Salt"
    assert fake_org.get_repo("repo-a").description == expected


@pytest.mark.usefixtures("testmode")
def test_managed_idempotent(res_states, fake_github, for_resource):
    with for_resource("testorg/repo-a"):
        ret = res_states["repo.managed"]("manage repo settings", description="Test repo repo-a")
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_managed_teams(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-b"):
        ret = res_states["repo.managed"]("manage repo teams", teams={"Team A": "push"})
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"teams_added": ["Team A"]}
    team_repos = fake_org.get_team("team-a").repos
    assert ("repo-b" in team_repos) is not testmode


@pytest.mark.usefixtures("testmode")
def test_managed_never_creates(res_states, fake_github, for_resource):
    before = len(fake_github.mutations())
    with for_resource("testorg/missing-repo"):
        ret = res_states["repo.managed"]("manage repo settings", description="Nope")
    assert ret["result"] is False
    assert not ret["changes"]
    assert "does not exist" in ret["comment"]
    assert len(fake_github.mutations()) == before
