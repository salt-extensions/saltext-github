import pytest


def test_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["ruleset.present"]("new-rules", ruleset_params={"enforcement": "active"})
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"created": "new-rules"}
    assert (len(fake_github.mutations()) == before) is testmode
    rulesets = fake_org.get_repo("repo-a").rulesets
    assert ("new-rules" in rulesets) is not testmode


@pytest.mark.usefixtures("testmode")
def test_present_idempotent(res_states, fake_github, for_resource):
    with for_resource("testorg/repo-a"):
        ret = res_states["ruleset.present"](
            "repo-rules", ruleset_params={"enforcement": "disabled"}
        )
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_absent(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-a"):
        ret = res_states["ruleset.absent"]("repo-rules")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "repo-rules"}
    rulesets = fake_org.get_repo("repo-a").rulesets
    assert ("repo-rules" in rulesets) is testmode
