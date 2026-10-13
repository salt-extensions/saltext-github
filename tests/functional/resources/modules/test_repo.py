import pytest
from salt.exceptions import CommandExecutionError


def test_ident(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert res_modules["repo.ident"]() == {
            "id": "testorg/repo-a",
            "owner": "testorg",
            "repo": "repo-a",
        }


def test_info_identity_routing(res_modules, for_resource):
    # The org repo and the user repo share the bare name; the resource ID
    # must disambiguate.
    with for_resource("testorg/repo-a"):
        assert res_modules["repo.info"]()["description"] == "Test repo repo-a"
    with for_resource("user1/repo-a"):
        assert res_modules["repo.info"]()["description"] == "User-owned repo-a"


def test_get_teams(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        teams = res_modules["repo.get_teams"]()
    assert list(teams) == ["Team A"]


def test_update(res_modules, for_resource, fake_org):
    with for_resource("testorg/repo-a"):
        res = res_modules["repo.update"](description="Managed by Salt")
    assert res["description"] == "Managed by Salt"
    assert fake_org.get_repo("repo-a").description == "Managed by Salt"


def test_update_privacy_change_gated(res_modules, for_resource):
    # The default profile enables allow_repo_privacy_changes; ensure the
    # gate is honored when the profile disables it.
    with for_resource("testorg/repo-a"):
        res_modules["repo.update"](private=True, profile="github")
        with pytest.raises(CommandExecutionError, match="allow_repo_privacy_changes"):
            res_modules["repo.update"](private=False, profile="github_noprivacy")
