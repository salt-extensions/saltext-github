"""
Operations on arbitrary GitHub user accounts, independent of any
organization membership.
"""

import logging

from saltext.github.utils.gh.client import api_request
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

# Public profile fields returned by get_info. Rendered via .get() since
# organization accounts miss some of them.
INFO_FIELDS = (
    "avatar_url",
    "bio",
    "blog",
    "company",
    "created_at",
    "email",
    "followers",
    "following",
    "html_url",
    "id",
    "location",
    "login",
    "name",
    "public_gists",
    "public_repos",
    "type",
    "updated_at",
    "url",
)


@api_request
def get_info(conn, login=None, *, expect=None):
    """
    Return the public profile of any user or organization account
    (distinguished via the returned ``type`` field).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        Account handle to look up. Defaults to the connection's owner,
        or to the token's user when ``expect`` is ``User``.

    expect
        Required account type, either ``User`` or ``Organization``.
        By default, both types are allowed.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the account does not exist or is not of the ``expect``-ed type.
    """
    if expect not in (None, "User", "Organization"):  # pragma: no cover
        raise ValueError(f"Invalid {expect=}. Valid: None, 'User', 'Organization'")
    if login is None and expect == "User":
        user = conn.auth_user
    else:
        # The /users/{login} endpoint resolves both account types
        user = conn.client.get_user(login or conn.owner)
    if expect is not None and user.type != expect:
        raise GitHubNotFoundError(f"{user.login} is not of type {expect}")
    data = user.raw_data
    return {fld: data.get(fld) for fld in INFO_FIELDS}


@api_request
def list_keys(conn, login=None):
    """
    Return the verified public SSH keys of any user as a list of
    mappings with ``id`` and ``key`` fields.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        User handle whose keys to list. Defaults to the user the
        connection's token belongs to.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the user does not exist.
    """
    user = conn.client.get_user(login or conn.auth_user.login)
    return [{"id": key.id, "key": key.key} for key in user.get_keys()]
