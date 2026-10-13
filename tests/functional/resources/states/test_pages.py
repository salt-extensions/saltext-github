import pytest


def test_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["pages.present"]("enable pages", build_type="workflow")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"created": "repo-a"}
    assert (len(fake_github.mutations()) == before) is testmode
    pages = fake_org.get_repo("repo-a").pages
    assert (pages is not None) is not testmode


@pytest.mark.usefixtures("testmode")
def test_present_idempotent(res_states, fake_github, for_resource):
    # repo-b has legacy pages from the default seed
    with for_resource("testorg/repo-b"):
        ret = res_states["pages.present"](
            "manage pages", build_type="legacy", source_branch="gh-pages", source_path="/"
        )
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_absent(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-b"):
        ret = res_states["pages.absent"]("disable pages")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "repo-b"}
    pages = fake_org.get_repo("repo-b").pages
    assert (pages is None) is not testmode
