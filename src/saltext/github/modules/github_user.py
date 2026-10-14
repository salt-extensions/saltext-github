"""
Look up information about GitHub **user** accounts.

.. versionadded:: 1.1.0

:depends: PyGithub python module

Configuration
-------------

This module reads its configuration from profiles, which are described
in the :ref:`configuration guide <github-configuration>`. All functions
accept a ``profile`` argument, defaulting to the ``github`` profile.
"""

import logging

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import users as gh_users

log = logging.getLogger(__name__)

__virtualname__ = "github_user"


def _get_conn(profile):
    return gh_profile.get_conn(profile, opts=__opts__, context=__context__)


def info(name=None, profile="github"):
    """
    Return the public profile of a user account. Fails when the account
    is an organization. Use :py:func:`github.account_info
    <saltext.github.modules.github.account_info>` to look up accounts of
    either type (note that it defaults to the profile's owner instead of
    the token's user).

    CLI Example:

    .. code-block:: bash

        salt-call github_user.info github-handle
        salt-call github_user.info  # the token's user

    name
        Login of the user to look up. Defaults to the user the
        profile's token belongs to.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_users.get_info(_get_conn(profile), name, expect="User")


def list_keys(name=None, profile="github"):
    """
    Return the verified public SSH keys of any user as a list of
    mappings with ``id`` and ``key`` fields, e.g. for use with the
    :py:func:`ssh_auth.present <salt.states.ssh_auth.present>` state.

    CLI Example:

    .. code-block:: bash

        salt-call github_user.list_keys github-handle
        salt-call github_user.list_keys  # the token's user

    name
        Login of the user whose keys to list. Defaults to the user the
        profile's token belongs to.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_users.list_keys(_get_conn(profile), name)
