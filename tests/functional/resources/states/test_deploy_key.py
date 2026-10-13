import pytest

from tests.support.github import DEPLOY_KEY_B


def test_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.present"]("new-key", DEPLOY_KEY_B)
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"created": "new-key"}
    assert (len(fake_github.mutations()) == before) is testmode
    titles = {key.title for key in fake_org.get_repo("repo-a").deploy_keys}
    assert ("new-key" in titles) is not testmode


@pytest.mark.usefixtures("testmode")
def test_present_idempotent(res_states, fake_github, for_resource, fake_org):
    existing = next(iter(fake_org.get_repo("repo-a").deploy_keys))
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.present"](
            "existing-key", existing.key, read_only=existing.read_only
        )
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_absent(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.absent"]("existing-key")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "existing-key"}
    assert (len(fake_github.mutations()) == before) is testmode
    titles = {key.title for key in fake_org.get_repo("repo-a").deploy_keys}
    assert ("existing-key" in titles) is testmode
