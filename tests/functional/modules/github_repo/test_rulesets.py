import pytest
from salt.exceptions import CommandExecutionError


def _ruleset_id(fake_org):
    return fake_org.get_repo("repo-a").rulesets["repo-rules"].id


def test_list_rulesets(github_repo):
    ret = github_repo.list_rulesets()
    assert [ruleset["name"] for ruleset in ret] == ["repo-rules"]


def test_get_ruleset(github_repo, fake_org):
    ret = github_repo.get_ruleset(_ruleset_id(fake_org))
    assert ret["name"] == "repo-rules"
    assert ret["enforcement"] == "disabled"
    assert ret["source_type"] == "Repository"


def test_get_ruleset_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_ruleset(1234)


def test_add_ruleset(github_repo, fake_org):
    ret = github_repo.add_ruleset({"name": "new-rules", "enforcement": "active"})
    assert ret["name"] == "new-rules"
    assert fake_org.get_repo("repo-a").rulesets["new-rules"].enforcement == "active"


def test_add_ruleset_missing_params(github_repo):
    with pytest.raises(CommandExecutionError, match="required"):
        github_repo.add_ruleset({"target": "branch"})


def test_update_ruleset(github_repo, fake_org):
    ret = github_repo.update_ruleset(_ruleset_id(fake_org), {"enforcement": "active"})
    assert ret["enforcement"] == "active"
    assert fake_org.get_repo("repo-a").rulesets["repo-rules"].enforcement == "active"


def test_delete_ruleset(github_repo, fake_org):
    assert github_repo.delete_ruleset(_ruleset_id(fake_org)) is True
    assert "repo-rules" not in fake_org.get_repo("repo-a").rulesets


def test_delete_ruleset_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.delete_ruleset(1234)
