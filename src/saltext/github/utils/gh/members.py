"""
Operations on GitHub organization members.
"""

import logging

from github.GithubException import UnknownObjectException

from saltext.github.utils.gh.client import api_request

log = logging.getLogger(__name__)


@api_request
def list_all(conn, *, owner=None, ignore_cache=False):
    """
    Return the logins of all members of an organization (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    owner
        Organization to target. Defaults to the connection's owner.

    ignore_cache
        Bypass the cached member list.
    """
    owner = owner or conn.owner
    key = ("members", owner.lower())
    if key not in conn.cache or ignore_cache:
        conn.cache[key] = [member.login for member in conn.get_org(owner).get_members()]
    return conn.cache[key]


@api_request
def get_info(conn, login, *, owner=None):
    """
    Return information about a user, including their organization
    membership state.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        User handle to look up.

    owner
        Organization to target. Defaults to the connection's owner.

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

    org = conn.get_org(owner)
    try:
        membership = user.get_organization_membership(org)
    except UnknownObjectException:
        ret["membership_state"] = "nonexistent"
        ret["in_org"] = False
        return ret

    ret["in_org"] = org.has_in_members(user)
    ret["membership_state"] = membership.state

    return ret


@api_request
def invite(conn, login, *, owner=None):
    """
    Invite a user into the organization. Returns whether the resulting
    membership state is ``pending``.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        User handle to invite.

    owner
        Organization to target. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the user does not exist.
    """
    user = conn.client.get_user(login)

    # There is no public method that also returns the resulting membership state
    _, data = conn.client.requester.requestJsonAndCheck(
        "PUT", conn.get_org(owner).url + "/memberships/" + user.login
    )

    return data.get("state") == "pending"


@api_request
def remove(conn, login, *, owner=None):
    """
    Remove a user from the organization (if they are a member).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    login
        User handle to remove.

    owner
        Organization to target. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the user does not exist.
    """
    user = conn.client.get_user(login)

    org = conn.get_org(owner)
    if org.has_in_members(user):
        org.remove_from_members(user)

    return True


@api_request
def list_without_mfa(conn, *, owner=None, ignore_cache=False):
    """
    Return the logins (lowercase) of all organization members without
    MFA turned on (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    owner
        Organization to target. Defaults to the connection's owner.

    ignore_cache
        Bypass the cached member list.
    """
    owner = owner or conn.owner
    key = ("members_without_mfa", owner.lower())
    if key not in conn.cache or ignore_cache:
        conn.cache[key] = [
            member.login.lower()
            for member in conn.get_org(owner).get_members(filter_="2fa_disabled")
        ]
    return conn.cache[key]
