"""
Resolution of Salt profile configuration into GitHub connections,
shared between the ``github``, ``github_org`` and ``github_repo``
execution modules as well as the ``github`` resource type.

Profiles are resolved directly from ``opts``, mirroring ``config.get``'s
lookup order: minion configuration, then grains, then pillar, then
master configuration (which reaches the minion via the master's
``pillar_opts`` setting, rendered under ``pillar["master"]``). SDB URIs
in profile values are rendered on access, like ``config.get`` renders
them. ``config.get`` itself cannot serve as the backend since it is
unavailable to parts of the resource subsystem (type discovery runs
before the minion's module loader exists).
"""

import logging
from pathlib import Path

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.cache import MISS
from saltext.github.utils.gh.cache import PersistentCache
from saltext.github.utils.gh.client import API_URL_DEFAULT
from saltext.github.utils.gh.client import GitHubConnection
from saltext.github.utils.gh.client import build_app_auth
from saltext.github.utils.gh.client import get_app_connection_ident
from saltext.github.utils.gh.client import get_connection_ident
from saltext.github.utils.gh.client import resolve_app_installation_id

log = logging.getLogger(__name__)

_UNSET = object()


def _render_value(value, opts, utils=None):
    """
    Render ``sdb://`` URIs in scalar configuration values, mirroring
    what ``config.get`` does for profile values.
    """
    if isinstance(value, str) and value.startswith("sdb://"):
        # Only required to resolve SDB URIs
        import salt.utils.sdb  # pylint: disable=import-outside-toplevel

        return salt.utils.sdb.sdb_get(value, opts, utils=utils)
    return value


def get_config_value(profile, config_name, *, opts, context=None, utils=None, default=_UNSET):
    """
    Return a profile's configuration value based on the supplied
    configuration name. See the module docstring for the lookup order
    and SDB handling; the first scope carrying the requested value wins.

    profile
        Profile name that contains configuration information.

    config_name
        Configuration item name to look up.

    opts
        The minion configuration (``__opts__``).

    context
        Pass ``__context__`` to cache rendered values, saving repeated
        SDB lookups.

    utils
        Pass ``__utils__`` when available to avoid building a fresh
        utils loader for SDB rendering.

    default
        Value to return when the profile does not carry the item.
        Without it, a missing item raises a ``CommandExecutionError``.
    """
    cache = None
    if context is not None:
        cache = context.setdefault("gh_profile", {}).setdefault(profile, {})
    if cache is None or config_name not in cache:
        pillar = opts.get("pillar") or {}
        master_pillar = pillar.get("master")
        scopes = (
            opts,
            opts.get("grains") or {},
            pillar,
            master_pillar if isinstance(master_pillar, dict) else {},
        )
        configs = [
            scope[profile]
            for scope in scopes
            if isinstance(scope.get(profile), dict) and scope[profile]
        ]
        if not configs:
            raise CommandExecutionError(
                f"Authentication information could not be found for the '{profile}' profile."
            )
        value = None
        for config in configs:
            found = config.get(config_name)
            if found is not None:
                value = _render_value(found, opts, utils=utils)
                break
        if cache is not None:
            cache[config_name] = value
    else:
        value = cache[config_name]

    if value is None:
        if default is not _UNSET:
            return default
        raise CommandExecutionError(
            f"The '{config_name}' parameter was not found in the '{profile}' profile."
        )
    return value


def get_api_url(profile, *, opts, context=None, utils=None):
    """
    Return the configured GitHub API base URL, defaulting to the public one.

    profile
        Profile name that contains configuration information.

    opts
        The minion configuration (``__opts__``).

    context
        Pass ``__context__`` to cache rendered values.

    utils
        Pass ``__utils__`` when available (SDB rendering).
    """
    return get_config_value(
        profile, "api_url", opts=opts, context=context, utils=utils, default=API_URL_DEFAULT
    ).rstrip("/")


def get_owner(profile, *, opts, context=None, utils=None):
    """
    Return the configured default repository owner: the profile's
    ``owner``, falling back to the legacy ``org_name`` alias. Returns
    ``None`` when neither is set, making the connection default to the
    token's user.

    profile
        Profile name that contains configuration information.

    opts
        The minion configuration (``__opts__``).

    context
        Pass ``__context__`` to cache rendered values.

    utils
        Pass ``__utils__`` when available (SDB rendering).
    """
    for key in ("owner", "org_name"):
        owner = get_config_value(
            profile, key, opts=opts, context=context, utils=utils, default=None
        )
        if owner is not None:
            return owner
    return None


def get_conn(profile, *, opts, context, utils=None):
    """
    Return a :class:`~saltext.github.utils.gh.client.GitHubConnection`
    for a profile, cached in ``context`` for performance.

    Unless the profile disables it (:ghconf:`cache`), the connection
    carries a :class:`~saltext.github.utils.gh.cache.PersistentCache`
    for slow-changing API data, surviving across processes.

    profile
        Profile name that contains configuration information.

    opts
        The minion configuration (``__opts__``).

    context
        Pass ``__context__``. Caches the connection and rendered
        profile values.

    utils
        Pass ``__utils__`` when available (SDB rendering).
    """
    profile_key = f"github.profile.{profile}"
    if profile_key in context:
        return context[profile_key]

    token = get_config_value(
        profile, "token", opts=opts, context=context, utils=utils, default=None
    )
    app_id = get_config_value(
        profile, "app_id", opts=opts, context=context, utils=utils, default=None
    )
    api_url = get_api_url(profile, opts=opts, context=context, utils=utils)
    owner = get_owner(profile, opts=opts, context=context, utils=utils)
    permissions = get_config_value(
        profile, "permissions", opts=opts, context=context, utils=utils, default=None
    )
    if token is not None and app_id is not None:
        raise CommandExecutionError(
            f"The '{profile}' profile specifies both 'token' and 'app_id', "
            "which are mutually exclusive."
        )
    if token is not None:
        if permissions is not None:
            raise CommandExecutionError(
                f"The 'permissions' parameter is only valid for GitHub App ('app_id') "
                f"profiles, but the '{profile}' profile uses token authentication."
            )
        # Hash the token to keep the secret out of context dumps
        ident = get_connection_ident(token, api_url)
    elif app_id is not None:
        if not owner:
            raise CommandExecutionError(
                f"GitHub App authentication requires the 'owner' parameter "
                f"in the '{profile}' profile."
            )
        if permissions is not None and not isinstance(permissions, dict):
            raise CommandExecutionError(
                f"The 'permissions' parameter of the '{profile}' profile must be a "
                "mapping of permission name to access level."
            )
        # Derived from the app's identity, not its short-lived
        # installation tokens - persistent cache banks survive rotation.
        # Differently restricted profiles must not share connections.
        ident = get_app_connection_ident(app_id, owner, api_url, permissions)
    else:
        raise CommandExecutionError(
            f"The '{profile}' profile is missing authentication credentials. "
            "Specify either 'token' or 'app_id' + 'private_key'/'private_key_path'."
        )
    conn_key = f"github.conn.{ident}"

    # This config is HTTP connection-independent. We should reuse a client, if it exists.
    cache_enabled = get_config_value(
        profile, "cache", opts=opts, context=context, utils=utils, default=True
    )

    if conn_key in context:
        other_conn = context[conn_key]
        store = ...
        if bool(other_conn.store) is not cache_enabled:
            store = PersistentCache(opts, ident) if cache_enabled else None
        context[profile_key] = context[conn_key].with_(owner=owner, store=store)
    else:
        store = PersistentCache(opts, ident) if cache_enabled else None
        auth = token
        if auth is None:
            auth = _get_app_auth(
                profile,
                app_id,
                owner=owner,
                api_url=api_url,
                permissions=permissions,
                store=store,
                opts=opts,
                context=context,
                utils=utils,
            )
        context[profile_key] = context[conn_key] = GitHubConnection(
            auth,
            owner,
            api_url=api_url,
            ident=ident,
            store=store,
        )
    return context[profile_key]


def _get_app_auth(
    profile, app_id, *, owner, api_url, permissions, store, opts, context, utils=None
):
    """
    Build the PyGithub auth object for a GitHub App profile. When the
    profile does not pin :ghconf:`installation_id`, the app's
    installation on ``owner`` is discovered via the API (cached in
    ``store``, when available).
    """
    private_key = get_config_value(
        profile, "private_key", opts=opts, context=context, utils=utils, default=None
    )
    private_key_path = get_config_value(
        profile, "private_key_path", opts=opts, context=context, utils=utils, default=None
    )
    if (private_key is None) is (private_key_path is None):
        raise CommandExecutionError(
            f"GitHub App authentication requires exactly one of 'private_key' or "
            f"'private_key_path', the '{profile}' profile specifies "
            f"{'both' if private_key is not None else 'neither'}."
        )
    if private_key_path is not None:
        try:
            private_key = Path(private_key_path).read_text(encoding="utf-8")
        except OSError as err:
            raise CommandExecutionError(
                f"Failed reading 'private_key_path' of the '{profile}' profile: {err}"
            ) from err
    installation_id = get_config_value(
        profile, "installation_id", opts=opts, context=context, utils=utils, default=None
    )
    if installation_id is None and store is not None:
        installation_id = store.get_meta("installation_id")
        if installation_id is MISS:
            installation_id = None
    if installation_id is None:
        installation_id = resolve_app_installation_id(app_id, private_key, owner, api_url)
        if store is not None:
            store.set_meta("installation_id", installation_id)
    return build_app_auth(app_id, private_key, installation_id, permissions)


def resource_decl(opts):
    """
    Return the ``github`` resource type's declaration from the resource
    pillar subtree (``{}`` when unset or not a mapping).

    opts
        The minion configuration (``__opts__``).
    """
    # Local import: the resource subsystem only exists in Salt >= 3008,
    # while this module is also imported on earlier releases.
    import salt.utils.resources  # pylint: disable=import-outside-toplevel

    decl = salt.utils.resources.pillar_resources_tree(opts).get("github")
    return decl if isinstance(decl, dict) else {}


def resource_profile(opts):
    """
    Return the default profile name configured in the ``github``
    resource declaration, defaulting to ``github``.

    opts
        The minion configuration (``__opts__``).
    """
    return resource_decl(opts).get("profile") or "github"


def resource_owners(opts):
    """
    Return the owners named in the ``github`` resource declaration as a
    list (an empty one when unset). The declaration's ``owners`` may be
    a plain list of owner names or a mapping of owner name to per-owner
    settings (``profile``, ``repos``, ``exclude``, ``include_archived``).

    opts
        The minion configuration (``__opts__``).
    """
    owners = resource_decl(opts).get("owners")
    if isinstance(owners, dict):
        return list(owners)
    return list(owners or [])


def _owner_settings(opts, owner):
    """
    Return one owner's settings mapping from the declaration's
    ``owners``, matched case-insensitively (``{}`` when the owners are
    a plain list or the owner carries no settings).
    """
    owners = resource_decl(opts).get("owners")
    if isinstance(owners, dict) and owner is not None:
        for name, settings in owners.items():
            if name.lower() == owner.lower() and isinstance(settings, dict):
                return settings
    return {}


def resource_owner_setting(opts, owner, key, default=None):
    """
    Return a declaration setting for one owner: the owner's own value
    from the ``owners`` mapping when set, otherwise the
    declaration-level value, otherwise ``default``.

    opts
        The minion configuration (``__opts__``).

    owner
        Owner (organization or user) login.

    key
        Setting name (``profile``, ``repos``, ``exclude``,
        ``include_archived``).

    default
        Value to return when neither the owner nor the declaration
        carries the setting.
    """
    value = _owner_settings(opts, owner).get(key)
    if value is None:
        value = resource_decl(opts).get(key)
    return value if value is not None else default


def resource_owner_profile(opts, owner):
    """
    Return the profile name to use for one owner's repositories: the
    owner's ``profile`` override from the declaration's ``owners``
    mapping when present, otherwise the declaration's default profile.
    Owner names are matched case-insensitively.

    opts
        The minion configuration (``__opts__``).

    owner
        Owner (organization or user) login.
    """
    return resource_owner_setting(opts, owner, "profile", "github")


def resource_profiles(opts):
    """
    Return all distinct profile names referenced by the ``github``
    resource declaration: the default one plus any per-owner overrides.

    opts
        The minion configuration (``__opts__``).
    """
    profiles = [resource_profile(opts)]
    owners = resource_decl(opts).get("owners")
    if isinstance(owners, dict):
        for settings in owners.values():
            if isinstance(settings, dict) and settings.get("profile"):
                if settings["profile"] not in profiles:
                    profiles.append(settings["profile"])
    return profiles


def resource_conn(opts, context, *, profile=None, owner=None, utils=None):
    """
    Return the :class:`~saltext.github.utils.gh.client.GitHubConnection`
    for a ``github`` resource context, resolved from ``opts``.

    opts
        The minion configuration (``__opts__``).

    context
        Cache mapping for the connection (``__context__``).

    profile
        Profile name override. When unset, the profile is resolved from
        the resource declaration: the targeted ``owner``'s override when
        declared, otherwise the declaration's default profile
        (``github`` when unset).

    owner
        Owner the connection is for, used to resolve per-owner profile
        overrides. Ignored when ``profile`` is passed.

    utils
        Pass ``__utils__`` when available (SDB rendering).
    """
    return get_conn(
        profile or resource_owner_profile(opts, owner), opts=opts, context=context, utils=utils
    )
