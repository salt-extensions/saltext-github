import logging

import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import grains_files as gh_grains_files
from saltext.github.utils.gh import repos as gh_repos
from saltext.github.utils.gh.exceptions import GitHubApiError

log = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# validate
# -------------------------------------------------------------------------


def _is_empty_dict(res):
    return isinstance(res, dict) and not res


def test_validate_unset():
    assert _is_empty_dict(gh_grains_files.validate(None))
    assert _is_empty_dict(gh_grains_files.validate({}))


def test_validate_normalization():
    spec = {
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
    }
    assert gh_grains_files.validate(spec) == {
        "copier": {
            "path": [".copier-answers.yml"],
            "include": None,
            "exclude": ["_*"],
        },
        "data": {
            "path": [".github/metadata.json", ".github/other-metadata.json"],
            "include": ["team", "org:config", ("service_tier", "service:tier")],
            "exclude": [],
        },
    }


def test_validate_include_mapping_shorthand():
    spec = gh_grains_files.validate(
        {"ns": {"path": "f", "include": {"a": "b:c", "d": "e", "f": None, "g*": ""}}}
    )
    assert spec["ns"]["include"] == [("a", "b:c"), ("d", "e"), "f", "g*"]


def test_validate_include_str():
    spec = gh_grains_files.validate({"ns": {"path": "f", "include": "foo*"}})
    assert spec["ns"]["include"] == ["foo*"]


def test_validate_accepts_root_namespace():
    assert gh_grains_files.validate({"_": {"path": "f"}}) == {
        "_": {"path": ["f"], "include": None, "exclude": []}
    }


@pytest.mark.parametrize(
    "spec,err",
    [
        (["foo"], "must be a mapping of namespace"),
        ({"owner": {"path": "f"}}, "shadows a builtin resource grain"),
        ({42: {"path": "f"}}, "must be non-empty strings"),
        ({"": {"path": "f"}}, "must be non-empty strings"),
        ({"ns": ["f"]}, "specification must be a mapping"),
        ({"ns": {}}, "'path' is required"),
        ({"ns": {"path": []}}, "'path' is required"),
        ({"ns": {"path": ["f", 2]}}, "'path' is required"),
        ({"ns": {"path": "f", "include": [{"a": "b", "c": "d"}]}}, "single-entry"),
        ({"ns": {"path": "f", "include": [{"a": 2}]}}, "single-entry"),
        ({"ns": {"path": "f", "include": [2]}}, "'include' entries must be"),
        ({"ns": {"path": "f", "exclude": [2]}}, "'exclude' must be a list"),
        ({"ns": {"path": "f", "includes": []}}, "unknown key"),
    ],
)
def test_validate_errors(spec, err):
    with pytest.raises(CommandExecutionError, match=err):
        gh_grains_files.validate(spec)


# -------------------------------------------------------------------------
# filter_content
# -------------------------------------------------------------------------


@pytest.fixture
def data():
    return {
        "team": "platform",
        "tier": 2,
        "_commit": "v1.2.3",
        "_src_path": "gh:org/tpl",
        "org": {
            "config": {"visibility": "public"},
            "other": True,
        },
        "service": {"tier": "gold", "name": "svc"},
    }


def test_filter_no_filters_deep_copies(data):
    res = gh_grains_files.filter_content(data)
    assert res == data
    assert res is not data
    res["org"]["config"]["visibility"] = "private"
    assert data["org"]["config"]["visibility"] == "public"


def test_filter_include_exact(data):
    assert gh_grains_files.filter_content(data, include=["team"]) == {"team": "platform"}


def test_filter_include_wildcard(data):
    assert gh_grains_files.filter_content(data, include=["t*"]) == {
        "team": "platform",
        "tier": 2,
    }


def test_filter_include_nested_path_preserves_nesting(data):
    assert gh_grains_files.filter_content(data, include=["org:config"]) == {
        "org": {"config": {"visibility": "public"}}
    }


def test_filter_include_intermediate_key_includes_subtree(data):
    assert gh_grains_files.filter_content(data, include=["org"]) == {
        "org": {"config": {"visibility": "public"}, "other": True}
    }


def test_filter_include_no_match(data):
    assert _is_empty_dict(gh_grains_files.filter_content(data, include=["nothing"]))


def test_filter_exclude_only(data):
    res = gh_grains_files.filter_content(data, exclude=["_*"])
    assert res == {
        "team": "platform",
        "tier": 2,
        "org": {"config": {"visibility": "public"}, "other": True},
        "service": {"tier": "gold", "name": "svc"},
    }


def test_filter_exclude_inside_included_subtree(data):
    assert gh_grains_files.filter_content(data, include=["org"], exclude=["org:other"]) == {
        "org": {"config": {"visibility": "public"}}
    }


def test_filter_exclude_empties_included_subtree(data):
    # The explicitly included (now empty) mapping is kept
    assert gh_grains_files.filter_content(data, include=["org"], exclude=["org:*"]) == {"org": {}}


def test_filter_exclude_at_depth():
    data = {"a": {"b": {"c": 1, "d": 2}}}
    assert gh_grains_files.filter_content(data, exclude=["a:b:c"]) == {"a": {"b": {"d": 2}}}


def test_filter_wildcard_crosses_segments(data):
    # fnmatch `*` is not segment-aware: `org*` also matches `org:other`
    # as an exclude at any depth
    assert gh_grains_files.filter_content(data, include=["service"], exclude=["service*name"]) == {
        "service": {"tier": "gold"}
    }


def test_filter_rename_scalar(data):
    assert gh_grains_files.filter_content(data, include=[("version", "_commit")]) == {
        "version": "v1.2.3"
    }


def test_filter_rename_subtree(data):
    res = gh_grains_files.filter_content(data, include=[("conf", "org:config")])
    assert res == {"conf": {"visibility": "public"}}
    res["conf"]["visibility"] = "mutated"
    assert data["org"]["config"]["visibility"] == "public"


def test_filter_rename_missing_source(data):
    assert _is_empty_dict(gh_grains_files.filter_content(data, include=[("x", "does:not:exist")]))


def test_filter_rename_through_scalar(data):
    assert _is_empty_dict(gh_grains_files.filter_content(data, include=[("x", "team:sub")]))


def test_filter_rename_immune_to_exclude(data):
    res = gh_grains_files.filter_content(
        data, include=[("version", "_commit")], exclude=["_*", "version"]
    )
    assert res == {"version": "v1.2.3"}


def test_filter_rename_first_definition_wins(data):
    res = gh_grains_files.filter_content(
        data, include=[("version", "_commit"), ("version", "org")], exclude=["_*", "version"]
    )
    assert res == {"version": "v1.2.3"}


def test_filter_rename_overrides_included_key(data):
    res = gh_grains_files.filter_content(data, include=["team", ("team", "service:name")])
    assert res == {"team": "svc"}


def test_filter_rename_to_nested_key(data):
    res = gh_grains_files.filter_content(data, include=[("nested:target", "service:name")])
    assert res == {"nested": {"target": "svc"}}


def test_filter_rename_source_is_literal(data):
    # No fnmatch in rename sources: `*` is a literal key
    assert _is_empty_dict(gh_grains_files.filter_content(data, include=[("x", "te*m")]))


def test_filter_earlier_rename_wins(data):
    res = gh_grains_files.filter_content(data, include=[("x", "team"), ("x", "service:name")])
    assert res == {"x": "platform"}


def _normalized(include=None, exclude=None):
    spec = gh_grains_files.validate({"ns": {"path": "f", "include": include, "exclude": exclude}})
    return spec["ns"]


def test_filter_with_normalized_rename_tuples(data):
    # filter_content consumes validate() output (tuples, not dicts)
    entry = _normalized(include=["team", {"version": "_commit"}])
    res = gh_grains_files.filter_content(data, include=entry["include"], exclude=entry["exclude"])
    assert res == {"team": "platform", "version": "v1.2.3"}


# -------------------------------------------------------------------------
# merge_grains
# -------------------------------------------------------------------------


def test_merge_grains_namespaces_and_root(caplog):
    grains = {
        "id": "o/r",
        "owner": "o",
        "owner2": "o2",
        "owner3": "o3",
        "nested_owner": {"should_not": {"be_replaced": True}},
    }
    custom = {
        "copier": {"a": 1},
        "_": {"team": "platform", "owner": "evil", "copier": "nope"},
        "nested:ns": {"success": True},
        "owner2": {"evil": True},
        "owner3:ns": {"evil": True},
        "nested_owner:should_not": {"be_replaced": False, "not_evil": True},
    }
    with caplog.at_level(logging.WARNING):
        res = gh_grains_files.merge_grains(grains, custom)
    assert res is grains
    # `_` keys land at the root; existing keys (builtin `owner`, earlier
    # namespace `copier`) are never overwritten
    assert grains == {
        "id": "o/r",
        "owner": "o",
        "owner2": "o2",
        "owner3": "o3",
        "copier": {"a": 1},
        "team": "platform",
        "nested": {"ns": {"success": True}},
        "nested_owner": {"should_not": {"be_replaced": True, "not_evil": True}},
    }
    assert "'copier' shadows an existing grain" in caplog.text
    assert "'owner' shadows an existing grain" in caplog.text
    assert "'owner2' shadows an existing grain" in caplog.text
    assert "'owner3:ns' shadows an existing grain" in caplog.text
    assert "'nested_owner:should_not:be_replaced' shadows an existing grain" in caplog.text


def test_merge_grains_first_wins():
    grains = {"id": "o/r"}
    custom = {"_": {"copier": "root-val"}, "copier": {"a": 1}}
    gh_grains_files.merge_grains(grains, custom)
    assert grains["copier"] == "root-val"


# -------------------------------------------------------------------------
# load_mapping
# -------------------------------------------------------------------------


def test_load_mapping_json():
    res = gh_grains_files.load_mapping('{"a": 1, "b": {"c": true}}', path="x")
    assert res == {"a": 1, "b": {"c": True}}


def test_load_mapping_yaml_types_normalized():
    res = gh_grains_files.load_mapping(
        "date: 2026-10-14\nflag: false\nempty: null\nnum: 2.5", path="x"
    )
    assert res["date"] == "2026-10-14"
    assert res["flag"] is False
    assert res["empty"] is None
    assert res["num"] == 2.5


@pytest.mark.parametrize("text", ["- a\n- b", "just a scalar", ""])
def test_load_mapping_non_mapping(text, caplog):
    with caplog.at_level(logging.WARNING):
        assert gh_grains_files.load_mapping(text, path="x") is None
    assert "does not contain a mapping" in caplog.text


def test_load_mapping_syntax_error(caplog):
    with caplog.at_level(logging.WARNING):
        assert gh_grains_files.load_mapping("a: [unclosed", path="x") is None
    assert "Failed parsing" in caplog.text


# -------------------------------------------------------------------------
# collect (fetch stubbed out)
# -------------------------------------------------------------------------


class FakeConn:
    owner = "testorg"


@pytest.fixture
def files(monkeypatch):
    contents = {}

    def fake_get_file_content(
        conn, name, path, *, owner=None, ignore_cache=False  # pylint: disable=unused-argument
    ):
        res = contents.get((owner, name, path))
        if isinstance(res, Exception):
            raise res
        return res

    monkeypatch.setattr(gh_repos, "get_file_content", fake_get_file_content)
    return contents


def test_collect_merges_first_wins(files):
    files[("testorg", "repo", "a.yml")] = "common: 1\nnested:\n  a: 1\nonly_a: true"
    files[("testorg", "repo", "b.yml")] = "common: 2\nnested:\n  b: 2\nonly_b: true"
    spec = gh_grains_files.validate({"ns": {"path": ["a.yml", "b.yml"]}})
    res = gh_grains_files.collect(FakeConn(), "repo", spec)
    # Very shallow merge: only undefined keys are merged and nested mappings are kept
    assert res == {"ns": {"common": 1, "nested": {"a": 1}, "only_a": True, "only_b": True}}


def test_collect_missing_files_skipped(files):
    files[("testorg", "repo", "b.yml")] = "found: true"
    spec = gh_grains_files.validate(
        {"ns": {"path": ["missing.yml", "b.yml"]}, "empty": {"path": "nope.yml"}}
    )
    res = gh_grains_files.collect(FakeConn(), "repo", spec)
    assert res == {"ns": {"found": True}}


def test_collect_fetch_error_skips_file(files, caplog):
    files[("testorg", "repo", "a.yml")] = GitHubApiError("500 boom", status=500)
    files[("testorg", "repo", "b.yml")] = "found: true"
    spec = gh_grains_files.validate({"ns": {"path": ["a.yml", "b.yml"]}})
    with caplog.at_level(logging.WARNING):
        res = gh_grains_files.collect(FakeConn(), "repo", spec)
    assert res == {"ns": {"found": True}}
    assert "Failed fetching 'a.yml'" in caplog.text


def test_collect_unparsable_file_skipped(files, caplog):
    files[("testorg", "repo", "a.yml")] = "- not\n- a\n- mapping"
    spec = gh_grains_files.validate({"ns": {"path": "a.yml"}})
    with caplog.at_level(logging.WARNING):
        assert _is_empty_dict(gh_grains_files.collect(FakeConn(), "repo", spec))


def test_collect_empty_filter_result_omitted(files):
    files[("testorg", "repo", "a.yml")] = "_commit: v1"
    spec = gh_grains_files.validate({"ns": {"path": "a.yml", "exclude": ["_*"]}})
    assert _is_empty_dict(gh_grains_files.collect(FakeConn(), "repo", spec))


def test_collect_applies_filters(files):
    files[("testorg", "repo", ".copier-answers.yml")] = "_commit: v1\nproject: salt"
    spec = gh_grains_files.validate(
        {"copier": {"path": ".copier-answers.yml", "include": [{"template_version": "_commit"}]}}
    )
    res = gh_grains_files.collect(FakeConn(), "repo", spec, owner="other")
    assert _is_empty_dict(res)  # seeded under testorg, fetched for owner "other"
    files[("other", "repo", ".copier-answers.yml")] = "_commit: v2\nproject: salt"
    res = gh_grains_files.collect(FakeConn(), "repo", spec, owner="other")
    assert res == {"copier": {"template_version": "v2"}}
