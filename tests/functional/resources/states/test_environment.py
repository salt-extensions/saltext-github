import pytest


def test_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["environment.present"]("staging", deployment_branches=["develop"])
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"]["created"] == "staging"
    assert ret["changes"]["deployment_branches"] == {"added": ["develop"], "removed": []}
    assert (len(fake_github.mutations()) == before) is testmode
    environments = fake_org.get_repo("repo-a").environments
    assert ("staging" in environments) is not testmode


@pytest.mark.usefixtures("testmode")
def test_present_idempotent(res_states, fake_github, for_resource):
    with for_resource("testorg/repo-a"):
        ret = res_states["environment.present"]("release", deployment_branches=["main"])
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_absent(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-a"):
        ret = res_states["environment.absent"]("release")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "release"}
    environments = fake_org.get_repo("repo-a").environments
    assert ("release" in environments) is testmode
