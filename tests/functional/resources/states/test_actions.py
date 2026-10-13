import pytest


def test_secret_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["actions.secret_present"]("NEW_SECRET", value="hunter3")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"created": "NEW_SECRET"}
    assert (len(fake_github.mutations()) == before) is testmode
    secrets = fake_org.get_repo("repo-a").secrets
    assert ("NEW_SECRET" in secrets) is not testmode


@pytest.mark.usefixtures("testmode")
def test_secret_present_existing(res_states, fake_github, for_resource):
    with for_resource("testorg/repo-a"):
        ret = res_states["actions.secret_present"]("EXISTING_SECRET", value="hunter3")
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_secret_absent(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-a"):
        ret = res_states["actions.secret_absent"]("EXISTING_SECRET")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "EXISTING_SECRET"}
    secrets = fake_org.get_repo("repo-a").secrets
    assert ("EXISTING_SECRET" in secrets) is testmode


def test_workflow_permissions_managed(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-a"):
        ret = res_states["actions.workflow_permissions_managed"](
            "workflow perms", default_workflow_permissions="read"
        )
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {
        "old": {"default_workflow_permissions": "write"},
        "new": {"default_workflow_permissions": "read"},
    }
    expected = "write" if testmode else "read"
    assert fake_org.get_repo("repo-a").default_workflow_permissions == expected
