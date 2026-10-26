"""
Tests for custom grains sourced from in-repo YAML/JSON files
(the ``grains_files`` resource declaration key).
"""

import copy
import logging

import pytest
import salt.loader
from salt.exceptions import CommandExecutionError

GRAINS_FILES = {
    "copier": {
        "path": ".copier-answers.yml",
        "exclude": ["_*"],
    },
    "data": {
        "path": [".github/metadata.json", ".github/other-metadata.json"],
        "include": [
            "team",
            "org:config",
            {"service_tier": "service:tier"},
        ],
    },
    # The special `_` namespace merges into the root grains
    "_": {
        "path": ".github/other-metadata.json",
        "include": ["extra", "owner", {"meta_team": "team"}],
    },
}


@pytest.fixture(scope="module")
def resource_decl():
    return {
        "profile": "github",
        "grains_files": GRAINS_FILES,
        "owners": {
            "testorg": {},
            "user1": {
                "grains_files": {
                    "copier": {
                        "path": ".copier-answers.yml",
                        # Mapping shorthand for rename-only includes
                        "include": {"template_version": "_commit"},
                    },
                },
            },
        },
    }


@pytest.fixture
def connection(res_funcs, res_opts):
    res_funcs["github.init"](res_opts)
    return res_funcs


def test_grains_custom_namespaces(connection, for_resource):
    with for_resource("testorg/repo-a"):
        grains = connection["github.grains"]()
    # Identity grains are unaffected
    assert grains["id"] == "testorg/repo-a"
    assert grains["default_branch"] == "main"
    # copier: everything but the excluded underscore keys
    assert grains["copier"] == {"project_name": "Repo A", "team": "platform"}
    # data: two files shallow-merged (earlier wins), include patterns
    # preserving nesting, rename exposed as flat key
    assert grains["data"] == {
        "team": "json-team",
        "org": {"config": {"visibility": "public"}},
        "service_tier": "gold",
    }
    # `_` namespace: merged into the root grains...
    assert grains["extra"] is True
    assert grains["meta_team"] == "other-team"
    # ...but never overwriting builtin identity grains
    assert grains["owner"] == "testorg"


def test_grains_all_files_missing(connection, for_resource):
    # repo-b carries none of the declared files
    with for_resource("testorg/repo-b"):
        grains = connection["github.grains"]()
    assert grains["repo"] == "repo-b"
    assert "copier" not in grains
    assert "data" not in grains


def test_grains_per_owner_override_replaces(connection, for_resource):
    """
    A per-owner ``grains_files`` fully replaces the declaration-level
    one: the override's include/rename applies instead of the default
    exclude, and the declaration's other namespaces don't apply.
    """
    with for_resource("user1/user-repo"):
        grains = connection["github.grains"]()
    assert grains["copier"] == {"template_version": "u9.9.9"}
    assert "data" not in grains
    assert "extra" not in grains


def test_grains_unparsable_file_skipped(connection, for_resource, fake_org, caplog):
    fake_org.get_repo("repo-a").get_file(".copier-answers.yml").update(content="a: [unclosed")
    with caplog.at_level(logging.WARNING):
        with for_resource("testorg/repo-a"):
            grains = connection["github.grains"]()
    assert "Failed parsing" in caplog.text
    assert "copier" not in grains
    # Identity grains and the other namespace survive
    assert grains["repo"] == "repo-a"
    assert grains["data"]["team"] == "json-team"


def test_grains_non_mapping_file_skipped(connection, for_resource, fake_org, caplog):
    fake_org.get_repo("repo-a").get_file(".copier-answers.yml").update(content="- a\n- b")
    with caplog.at_level(logging.WARNING):
        with for_resource("testorg/repo-a"):
            grains = connection["github.grains"]()
    assert "does not contain a mapping" in caplog.text
    assert "copier" not in grains
    assert grains["repo"] == "repo-a"


def test_init_invalid_grains_files(res_funcs, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["grains_files"] = {"owner": {"path": "f"}}
    with pytest.raises(CommandExecutionError, match="shadows a builtin"):
        res_funcs["github.init"](opts)


def test_init_invalid_per_owner_grains_files(res_funcs, res_opts):
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"]["user1"]["grains_files"] = {"ns": {}}
    with pytest.raises(CommandExecutionError, match="'path' is required"):
        res_funcs["github.init"](opts)


def test_grains_file_fetches_cached(connection, for_resource, fake_github):
    with for_resource("testorg/repo-a"):
        connection["github.grains"]()
        # 3 distinct paths: the `_` namespace reuses the `data`
        # namespace's cached fetch of other-metadata.json
        assert len(fake_github.filter_requests(path="*/contents/*")) == 3
        connection["github.grains"]()
    # Served from the connection cache, no further requests
    assert len(fake_github.filter_requests(path="*/contents/*")) == 3


def test_grains_negative_fetches_cached(connection, for_resource, fake_github):
    with for_resource("testorg/repo-b"):
        connection["github.grains"]()
        # All three declared paths are missing and were tried once
        assert len(fake_github.filter_requests(path="*/contents/*")) == 3
        connection["github.grains"]()
    assert len(fake_github.filter_requests(path="*/contents/*")) == 3


def test_grains_refresh_refetches_files(connection, for_resource, fake_org):
    with for_resource("testorg/repo-a"):
        assert connection["github.grains"]()["copier"]["team"] == "platform"
        fake_org.get_repo("repo-a").get_file(".copier-answers.yml").update(
            content="team: replatformed"
        )
        # Plain grains() serves from the warmed cache
        assert connection["github.grains"]()["copier"]["team"] == "platform"
        refreshed = connection["github.grains_refresh"]()
    assert refreshed["copier"] == {"team": "replatformed"}


def test_grains_per_owner_empty_disables(res_opts, utils_loader, for_resource):
    """
    A per-owner ``grains_files: {}`` is a full override as well,
    disabling custom grains for that owner.
    """
    opts = copy.deepcopy(res_opts)
    opts["pillar"]["resources"]["github"]["owners"]["testorg"] = {"grains_files": {}}
    cold_context = {}
    funcs = salt.loader.resource(
        opts,
        utils=utils_loader,
        context=cold_context,
        loaded_base_name=f"{__name__}.empty",
    )
    funcs["github.init"](opts)
    with for_resource("testorg/repo-a"):
        grains = funcs["github.grains"]()
    assert "copier" not in grains
    assert "data" not in grains
    assert grains["repo"] == "repo-a"
