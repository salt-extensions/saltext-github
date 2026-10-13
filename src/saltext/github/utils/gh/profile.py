"""
Resolution of Salt profile configuration into GitHub connections,
shared between the ``github``, ``github_org`` and ``github_repo``
execution modules.
"""

import hashlib
import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.client import API_URL_DEFAULT
from saltext.github.utils.gh.client import GitHubConnection

log = logging.getLogger(__name__)


def get_config_value(profile, config_name, *, __salt__, __context__):
    """
    Return a profile's configuration value based on the supplied
    configuration name. Values are rendered via ``config.get``
    (resolving SDB URIs) and cached in ``context``.

    profile
        Profile name that contains configuration information.

    config_name
        Configuration item name to look up.

    __salt__
        Pass ``__salt__``.

    __context__
        Pass ``__context__``.
    """
    if "gh_profile" not in __context__ or profile not in __context__["gh_profile"]:
        if not __salt__["config.get"](profile):
            raise CommandExecutionError(
                f"Authentication information could not be found for the '{profile}' profile."
            )
        __context__.setdefault("gh_profile", {})[profile] = {}

    cache = __context__["gh_profile"][profile]
    if config_name not in cache:
        # Unlike config.option, config.get resolves SDB URIs in scalar values,
        # hence request each value separately and cache the rendered result.
        cache[config_name] = __salt__["config.get"](f"{profile}:{config_name}", default=None)

    config_value = cache[config_name]
    if config_value is None:
        raise CommandExecutionError(
            f"The '{config_name}' parameter was not found in the '{profile}' profile."
        )

    return config_value


def get_api_url(profile, *, __salt__, __context__):
    """
    Return the configured GitHub API base URL, defaulting to the public one.

    profile
        Profile name that contains configuration information.

    __salt__
        Pass ``__salt__``.

    __context__
        Pass ``__context__``.
    """
    try:
        return get_config_value(
            profile, "api_url", __salt__=__salt__, __context__=__context__
        ).rstrip("/")
    except CommandExecutionError:
        return API_URL_DEFAULT


def get_owner(profile, *, __salt__, __context__):
    """
    Return the configured default repository owner: the profile's
    ``owner``, falling back to the legacy ``org_name`` alias. Returns
    ``None`` when neither is set, making the connection default to the
    token's user.

    profile
        Profile name that contains configuration information.

    __salt__
        Pass ``__salt__``.

    __context__
        Pass ``__context__``.
    """
    for key in ("owner", "org_name"):
        try:
            return get_config_value(profile, key, __salt__=__salt__, __context__=__context__)
        except CommandExecutionError:
            continue
    return None


def get_conn(profile, *, __salt__, __context__):
    """
    Return a :class:`~saltext.github.utils.gh.client.GitHubConnection`
    for a profile, cached in ``context`` for performance.

    profile
        Profile name that contains configuration information.

    salt
        Pass ``__salt__``.

    context
        Pass ``__context__``.
    """
    token = get_config_value(profile, "token", __salt__=__salt__, __context__=__context__)
    owner = get_owner(profile, __salt__=__salt__, __context__=__context__)
    api_url = get_api_url(profile, __salt__=__salt__, __context__=__context__)
    # Hash the token to keep the secret out of context dumps
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    key = f"github.{token_hash}:{owner}:{api_url}"

    if key not in __context__:
        __context__[key] = GitHubConnection(token, owner, api_url=api_url)
    return __context__[key]
