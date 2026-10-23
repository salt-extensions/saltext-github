"""
Tests for the ``state`` execution module override, which makes
``state.apply``/``state.single`` & friends dispatchable to ``github``
resources (the per-resource loader is deny-by-default, so without the
override Salt reports them as unsupported for the resource type).
"""

import pytest

EXPOSED = (
    "state.apply",
    "state.highstate",
    "state.show_sls",
    "state.single",
    "state.sls",
    "state.sls_id",
)

UNEXPOSED = (
    "state.clear_cache",
    "state.disable",
    "state.enable",
    "state.event",
    "state.pkg",
)


@pytest.fixture(params=(False, True))
def testmode(request):
    return request.param


def test_exposed_functions(res_modules):
    for fun in EXPOSED:
        assert fun in res_modules


def test_unexposed_functions(res_modules):
    """
    Only the state-application surface is re-exported; minion-local
    plumbing must not be reachable via the resource loader.
    """
    # Ensure the module is loaded before checking for missing functions
    assert "state.single" in res_modules
    for fun in UNEXPOSED:
        assert fun not in res_modules


def test_single_override_state(res_modules, fake_org, for_resource, testmode):
    """
    ``state.single`` runs this extension's state overrides against the
    targeted repository.
    """
    with for_resource("testorg/repo-a"):
        ret = res_modules["state.single"](
            "label.present", name="release", color="#00FF00", test=testmode
        )
    assert isinstance(ret, dict)
    chunk = ret["label_|-release_|-release_|-present"]
    assert chunk["result"] is not False
    assert (chunk["result"] is None) is testmode
    assert chunk["changes"] == {"created": "release"}
    labels = fake_org.get_repo("repo-a").labels
    assert ("release" in labels) is not testmode


@pytest.mark.usefixtures("testmode")
def test_single_override_state_idempotent(res_modules, fake_github, for_resource):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_modules["state.single"]("label.present", name="bug", color="#D73A4A")
    chunk = ret["label_|-bug_|-bug_|-present"]
    assert chunk["result"] is True
    assert not chunk["changes"]
    assert len(fake_github.mutations()) == before


def test_single_stock_state(res_modules, for_resource):
    """
    Stock state modules are available unchanged in the resource context.
    """
    with for_resource("testorg/repo-a"):
        ret = res_modules["state.single"]("test.succeed_without_changes", name="sanity")
    chunk = ret["test_|-sanity_|-sanity_|-succeed_without_changes"]
    assert chunk["result"] is True


@pytest.mark.skip_on_windows(
    reason="state.sls calls cmd.run there, which is not exposed in the resource context"
)
def test_sls(res_modules, fake_org, state_tree, for_resource, testmode):
    """
    ``state.sls`` compiles from the managing minion's fileserver and runs
    the chunks through the per-resource loader.
    """
    sls_contents = """
    managed label:
      label.present:
        - name: from-sls
        - color: "#0000FF"
    """
    with pytest.helpers.temp_file("gh_label.sls", sls_contents, state_tree):
        with for_resource("testorg/repo-a"):
            ret = res_modules["state.sls"]("gh_label", test=testmode)
    assert isinstance(ret, dict)
    chunk = ret["label_|-managed label_|-from-sls_|-present"]
    assert chunk["result"] is not False
    assert (chunk["result"] is None) is testmode
    assert chunk["changes"] == {"created": "from-sls"}
    labels = fake_org.get_repo("repo-a").labels
    assert ("from-sls" in labels) is not testmode


def test_show_sls(res_modules, state_tree, for_resource):
    sls_contents = """
    managed label:
      label.present:
        - name: from-sls
        - color: "#0000FF"
    """
    with pytest.helpers.temp_file("gh_label.sls", sls_contents, state_tree):
        with for_resource("testorg/repo-a"):
            ret = res_modules["state.show_sls"]("gh_label")
    assert isinstance(ret, dict)
    assert "managed label" in ret
    assert "label" in ret["managed label"]
