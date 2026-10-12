import pytest
from salt.exceptions import CommandExecutionError


def test_list_rulesets(github_org):
    ret = github_org.list_rulesets()
    assert [ruleset["name"] for ruleset in ret] == ["org-rules"]


def test_get_ruleset(github_org, fake_org):
    existing = fake_org.rulesets["org-rules"]
    ret = github_org.get_ruleset(existing.id)
    assert ret["name"] == "org-rules"
    assert ret["enforcement"] == "active"
    assert ret["source_type"] == "Organization"


def test_get_ruleset_missing(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.get_ruleset(1234)


def test_add_ruleset(github_org, fake_org):
    ret = github_org.add_ruleset({"name": "new-rules", "enforcement": "evaluate"})
    assert ret["name"] == "new-rules"
    assert fake_org.rulesets["new-rules"].enforcement == "evaluate"


def test_add_ruleset_missing_params(github_org):
    with pytest.raises(CommandExecutionError, match="required"):
        github_org.add_ruleset({"target": "branch"})


def test_update_ruleset(github_org, fake_org):
    existing = fake_org.rulesets["org-rules"]
    ret = github_org.update_ruleset(existing.id, {"enforcement": "disabled"})
    assert ret["enforcement"] == "disabled"
    assert fake_org.rulesets["org-rules"].enforcement == "disabled"


def test_delete_ruleset(github_org, fake_org):
    existing = fake_org.rulesets["org-rules"]
    assert github_org.delete_ruleset(existing.id) is True
    assert "org-rules" not in fake_org.rulesets


def test_delete_ruleset_missing(github_org):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_org.delete_ruleset(1234)
