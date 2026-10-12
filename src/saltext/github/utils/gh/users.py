"""
Operations on GitHub organization members.
"""

import logging

from github.GithubException import UnknownObjectException

from saltext.github.utils.gh.client import api_request

log = logging.getLogger(__name__)


@api_request
def list_members(conn, ignore_cache=False):
    """
    Return the logins of all members of the organization (cached).

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ignore_cache
        Bypass the cached member list.
    """
    if "users" not in conn.cache or ignore_cache:
        conn.cache["users"] = [member.login for member in conn.org.get_members()]
    return conn.cache["users"]


@api_request
def get_user_info(conn, login):
    """
    Return information about a user, including their organization
    membership state.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        The login of the user to look up.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the user does not exist.
    """
    user = conn.client.get_user(login)

    ret = {
        "company": user.company,
        "created_at": user.created_at,
        "email": user.email,
        "html_url": user.html_url,
        "id": user.id,
        "login": user.login,
        "name": user.name,
        "type": user.type,
        "url": user.url,
    }

    try:
        membership = user.get_organization_membership(conn.org)
    except UnknownObjectException:
        ret["membership_state"] = "nonexistent"
        ret["in_org"] = False
        return ret

    ret["in_org"] = conn.org.has_in_members(user)
    ret["membership_state"] = membership.state

    return ret


@api_request
def invite_member(conn, login):
    """
    Invite a user into the organization. Returns whether the resulting
    membership state is ``pending``.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        The login of the user to invite.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the user does not exist.
    """
    user = conn.client.get_user(login)

    # There is no public method that also returns the resulting membership state
    _, data = conn.client.requester.requestJsonAndCheck(
        "PUT", conn.org.url + "/memberships/" + user.login
    )

    return data.get("state") == "pending"


@api_request
def remove_member(conn, login):
    """
    Remove a user from the organization. Returns whether the user is no
    longer a member afterwards.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        The login of the user to remove.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the user does not exist.
    """
    user = conn.client.get_user(login)

    if conn.org.has_in_members(user):
        conn.org.remove_from_members(user)

    return not conn.org.has_in_members(user)


@api_request
def list_members_without_mfa(conn, ignore_cache=False):
    """
    Return the logins (lowercase) of all organization members without
    MFA turned on (cached).

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ignore_cache
        Bypass the cached member list.
    """
    if "members_without_mfa" not in conn.cache or ignore_cache:
        conn.cache["members_without_mfa"] = [
            member.login.lower() for member in conn.org.get_members(filter_="2fa_disabled")
        ]
    return conn.cache["members_without_mfa"]
