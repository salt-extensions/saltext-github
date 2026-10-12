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


def get_config_value(profile, config_name, *, salt, context):
    """
    Return a profile's configuration value based on the supplied
    configuration name. Values are rendered via ``config.get``
    (resolving SDB URIs) and cached in ``context``.

    profile
        Profile name that contains configuration information.

    config_name
        Configuration item name to look up.

    salt
        ``__salt__`` dunder of the calling module.

    context
        ``__context__`` dunder of the calling module.
    """
    if "gh_profile" not in context or profile not in context["gh_profile"]:
        if not salt["config.get"](profile):
            raise CommandExecutionError(
                f"Authentication information could not be found for the '{profile}' profile."
            )
        context.setdefault("gh_profile", {})[profile] = {}

    cache = context["gh_profile"][profile]
    if config_name not in cache:
        # Unlike config.option, config.get resolves SDB URIs in scalar values,
        # hence request each value separately and cache the rendered result.
        cache[config_name] = salt["config.get"](f"{profile}:{config_name}", default=None)

    config_value = cache[config_name]
    if config_value is None:
        raise CommandExecutionError(
            f"The '{config_name}' parameter was not found in the '{profile}' profile."
        )

    return config_value


def get_api_url(profile, *, salt, context):
    """
    Return the configured GitHub API base URL, defaulting to the public one.

    profile
        Profile name that contains configuration information.

    salt
        ``__salt__`` dunder of the calling module.

    context
        ``__context__`` dunder of the calling module.
    """
    try:
        return get_config_value(profile, "api_url", salt=salt, context=context).rstrip("/")
    except CommandExecutionError:
        return API_URL_DEFAULT


def get_conn(profile, *, salt, context):
    """
    Return a :class:`~saltext.github.utils.gh.client.GitHubConnection`
    for a profile, cached in ``context`` for performance.

    profile
        Profile name that contains configuration information.

    salt
        ``__salt__`` dunder of the calling module.

    context
        ``__context__`` dunder of the calling module.
    """
    token = get_config_value(profile, "token", salt=salt, context=context)
    org_name = get_config_value(profile, "org_name", salt=salt, context=context)
    api_url = get_api_url(profile, salt=salt, context=context)
    # Hash the token to keep the secret out of context dumps
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    key = f"github.{token_hash}:{org_name}:{api_url}"

    if key not in context:
        context[key] = GitHubConnection(token, org_name, api_url=api_url)
    return context[key]
