"""
Custom repository grains sourced from in-repo YAML/JSON files, as
declared via the :ghconf:`resource:grains_files` key of the ``github``
resource type.

A declaration maps grain namespaces to file specifications::

    grains_files:
      copier:
        path: .copier-answers.yml
        exclude:
          - "_*"
      data:
        path:
          - .github/metadata.json
          - .github/other-metadata.json
        include:
          - team
          - org:config
          - service_tier: service:tier

``include``/``exclude`` entries are :py:mod:`fnmatch` patterns matched
case-sensitively against colon-delimited key paths, the same idiom Salt
uses for grain targeting. Note that ``*`` is not segment-aware (it can
cross ``:`` boundaries) and keys containing ``:`` cannot be addressed.
Mapping entries in ``include`` rename: the value at the exact source
path (scalar or subtree) is exposed under the new name as a flat
namespace key. Renames are not subject to ``exclude``. A plain mapping
as the ``include`` value is shorthand for a rename-only list.

The special ``_`` namespace merges its keys into the root grains level
instead of below a namespace key. Custom grains never overwrite
existing ones – the builtin identity grains and earlier namespaces
always win.
"""

import copy
import fnmatch
import json
import logging

import salt.utils.data
import salt.utils.dictupdate
import salt.utils.yaml
import yaml
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import repos as gh_repos
from saltext.github.utils.gh.exceptions import GitHubApiError

log = logging.getLogger(__name__)

#: Grain keys provided by the resource type itself. ``grains_files``
#: namespaces must not shadow them — the resource identity is not
#: overridable by repository contents.
RESERVED_KEYS = frozenset(
    {
        "id",
        "owner",
        "repo",
        "full_name",
        "private",
        "visibility",
        "fork",
        "archived",
        "disabled",
        "is_template",
        "default_branch",
        "language",
        "license",
        "topics",
        "custom_properties",
        "html_url",
        "clone_url",
        "ssh_url",
        "description",
        "homepage",
        "created_at",
        "has_discussions",
        "has_pages",
        "has_projects",
    }
)

_SPEC_KEYS = frozenset({"path", "include", "exclude"})

#: Sentinel for failed path traversal (``None`` is a valid value).
_MISSING = object()


def _invalid(namespace, msg):
    return CommandExecutionError(f"Invalid grains_files namespace '{namespace}': {msg}")


def validate(spec):
    """
    Normalize and validate a ``grains_files`` declaration value.

    Returns the normalized form, a mapping of namespace to
    ``{"path": [str, ...], "include": [str | (new_name, source), ...] | None,
    "exclude": [str, ...]}``. Raises a ``CommandExecutionError`` when the
    declaration is malformed.

    spec
        The declaration value. ``None`` is treated as unset.
    """
    if spec is None:
        return {}
    if not isinstance(spec, dict):
        raise CommandExecutionError(
            "grains_files must be a mapping of namespace to file specification"
        )
    normalized = {}
    for namespace, entry in spec.items():
        if not isinstance(namespace, str) or not namespace:
            raise CommandExecutionError(
                f"grains_files namespaces must be non-empty strings, got: {namespace!r}"
            )
        if namespace in RESERVED_KEYS:
            raise _invalid(namespace, "shadows a builtin resource grain")
        if not isinstance(entry, dict):
            raise _invalid(namespace, "the file specification must be a mapping")
        if unknown := set(entry) - _SPEC_KEYS:
            raise _invalid(namespace, f"unknown key(s): {', '.join(sorted(unknown))}")
        paths = entry.get("path")
        if isinstance(paths, str):
            paths = [paths]
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(path, str) and path for path in paths)
        ):
            raise _invalid(namespace, "'path' is required and must be a string or list of strings")
        normalized[namespace] = {
            "path": paths,
            "include": _validate_include(namespace, entry.get("include")),
            "exclude": _validate_exclude(namespace, entry.get("exclude")),
        }
    return normalized


def _validate_include(namespace, include):
    if include is None:
        return None
    if isinstance(include, str):
        include = [include]
    elif isinstance(include, dict):
        # Mapping shorthand for rename includes (unset values still imply regular inclusions)
        include = [
            {new_name: source} if source else new_name for new_name, source in include.items()
        ]
    elif not isinstance(include, list):
        raise _invalid(namespace, "'include' must be a list, string or mapping")
    res = []
    for item in include:
        if isinstance(item, str) and item:
            res.append(item)
            continue
        if isinstance(item, dict) and len(item) == 1:
            ((new_name, source),) = item.items()
            if isinstance(new_name, str) and new_name and isinstance(source, str) and source:
                res.append((new_name, source))
                continue
        raise _invalid(
            namespace,
            "'include' entries must be patterns or single-entry "
            f"'new_name: source:path' renames, got: {item!r}",
        )
    return res


def _validate_exclude(namespace, exclude):
    if exclude is None:
        return []
    if isinstance(exclude, str):
        return [exclude]
    if not isinstance(exclude, list) or not all(isinstance(pat, str) and pat for pat in exclude):
        raise _invalid(namespace, "'exclude' must be a list of patterns")
    return list(exclude)


def load_mapping(text, *, path):
    """
    Parse a file's text as YAML (which includes JSON) into a mapping of
    JSON-plain values, or ``None`` (logging a warning) when the text does
    not parse or does not represent a mapping.

    text
        The file content.

    path
        Identifier of the file's origin, used in log messages.
    """
    try:
        parsed = salt.utils.yaml.safe_load(text)
    except yaml.YAMLError as err:
        log.warning("Failed parsing '%s' as YAML/JSON: %s", path, err)
        return None
    if not isinstance(parsed, dict):
        log.warning("File '%s' does not contain a mapping, skipping", path)
        return None
    try:
        # Normalize to JSON-plain types (e.g. YAML timestamps -> strings)
        return json.loads(json.dumps(parsed, default=str))
    except (TypeError, ValueError) as err:
        log.warning("Failed normalizing the contents of '%s': %s", path, err)
        return None


def filter_content(data, include=None, exclude=None):
    """
    Apply a normalized (per :func:`validate`) include/exclude
    specification to a parsed file mapping and return the result.

    data
        The parsed file content.

    include
        Normalized include entries: fnmatch patterns against
        colon-delimited key paths (a match includes the whole subtree,
        preserving nesting) and ``(new_name, source)`` rename tuples
        (exact source path, value exposed as flat ``new_name`` key).
        ``None`` includes everything.

    exclude
        Fnmatch patterns pruning matching key paths at any depth after
        includes. Does not apply to renames.
    """
    patterns = None
    # need to make sure the first rename wins for consistency
    renames = {}

    if include is not None:
        patterns = []
        for item in include:
            if isinstance(item, str):
                patterns.append(item)
            else:
                new_name, source = item
                if new_name not in renames:
                    renames[new_name] = source
    result = _filter_node(data, "", patterns, exclude or [], patterns is None)
    for new_name, source in renames.items():
        source = source or new_name  # unnormalized mapping-style include with no rename intention
        value = salt.utils.data.traverse_dict_and_list(data, source, ..., delimiter=":")
        if value is not ...:
            salt.utils.dictupdate.set_dict_key_value(
                result, new_name, copy.deepcopy(value), delimiter=":"
            )
    return result


def _filter_node(node, prefix, patterns, excludes, included_parent):
    result = {}
    for key, value in node.items():
        path = f"{prefix}:{key}" if prefix else str(key)
        if any(fnmatch.fnmatchcase(path, pat) for pat in excludes):
            continue
        included = included_parent or any(fnmatch.fnmatchcase(path, pat) for pat in patterns or ())
        if isinstance(value, dict):
            # Recurse into non-included subtrees as well since deeper
            # paths can still match an include pattern.
            sub = _filter_node(value, path, patterns, excludes, included)
            if included or sub:
                result[key] = sub
        elif included:
            result[key] = copy.deepcopy(value)
    return result


def merge_grains(grains, custom):
    """
    Merge collected (per :func:`collect`) custom grains into a grains
    mapping and return it. The special ``_`` namespace contributes its
    keys at the root level, other namespaces become a single key each.
    Keys already present – the builtin identity grains or earlier
    namespaces – are never overwritten (logged and skipped).

    grains
        The grains mapping to merge into (mutated).

    custom
        Mapping of namespace to grain data.
    """
    for namespace, data in custom.items():
        items = data.items() if namespace == "_" else ((namespace, data),)
        for key, value in items:
            ns_its = key.split(":")
            ns_its.reverse()

            tgt = grains
            ns_it = ns_its.pop()
            while ns_its:
                if ns_it not in tgt:
                    tgt[ns_it] = {}
                elif not isinstance(tgt[ns_it], dict):
                    log.warning("Custom grain '%s' shadows an existing grain, skipping", key)
                    break
                tgt = tgt[ns_it]
                ns_it = ns_its.pop()
            else:
                if ns_it not in tgt:
                    tgt[ns_it] = value
                    continue
                if not isinstance(tgt[ns_it], dict) or not isinstance(value, dict):
                    log.warning("Custom grain '%s' shadows an existing grain, skipping", key)
                    continue
                for k, v in value.items():
                    if k not in tgt[ns_it]:
                        tgt[ns_it][k] = v
                        continue
                    log.warning("Custom grain '%s:%s' shadows an existing grain, skipping", key, k)
    return grains


def collect(conn, repo_name, spec, *, owner=None):
    """
    Fetch, parse, merge and filter all namespaces of a normalized (per
    :func:`validate`) ``grains_files`` specification for one repository.

    Returns a mapping of namespace to grain data; namespaces without any
    resulting data are omitted. Per-file and per-namespace problems are
    logged and skipped, never raised.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    spec
        The normalized ``grains_files`` specification.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    owner = owner or conn.owner
    ret = {}
    for namespace, entry in spec.items():
        try:
            merged = {}
            for path in entry["path"]:
                try:
                    content = gh_repos.get_file_content(conn, repo_name, path, owner=owner)
                except GitHubApiError as err:
                    log.warning("Failed fetching '%s' from %s/%s: %s", path, owner, repo_name, err)
                    continue
                if content is None:
                    continue
                parsed = load_mapping(content, path=f"{owner}/{repo_name}:{path}")
                if parsed is not None:
                    merged.update((k, v) for k, v in parsed.items() if k not in merged)
            if not merged:
                continue
            data = filter_content(merged, include=entry["include"], exclude=entry["exclude"])
            if data:
                ret[namespace] = data
        except Exception as err:  # pylint: disable=broad-except
            log.warning(
                "Failed collecting custom grains namespace '%s' for %s/%s: %s",
                namespace,
                owner,
                repo_name,
                err,
            )
    return ret
