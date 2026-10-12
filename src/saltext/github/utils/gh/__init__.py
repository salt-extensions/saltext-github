"""
Connection library for GitHub.

The submodules of this package provide reusable primitives for talking
to the GitHub API on behalf of an organization, built around
:class:`~saltext.github.utils.gh.client.GitHubConnection`.
They raise :class:`~saltext.github.utils.gh.exceptions.GitHubApiError`
(or its more specific subclass
:class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`)
on API errors.
"""

import logging

import salt.utils.http
import salt.utils.json

from saltext.github.utils.gh.exceptions import GitHubApiError  # noqa: F401
from saltext.github.utils.gh.exceptions import GitHubNotFoundError  # noqa: F401

log = logging.getLogger(__name__)


def get_user_pubkeys(users):
    """
    Retrieve a set of public keys from GitHub for the specified list of users.
    Expects input in list format. Optionally, a value in the list may be a dict
    whose value is a list of key IDs to be returned. If this is not done, then
    all keys will be returned.

    Some example data structures that coupld be passed in would look like:

    .. code-block:: yaml

        ['user1', 'user2', 'user3']

        [
            'user1': [
                '12345',
                '67890',
            ],
            'user2',
            'user3',
        ]
    """
    if not isinstance(users, list):
        return {"Error": "A list of users is expected"}

    ret = {}
    for user in users:
        key_ids = []
        if isinstance(user, dict):
            tmp_user = next(iter(user.keys()))
            key_ids = user[tmp_user]
            user = tmp_user

        url = f"https://api.github.com/users/{user}/keys"
        result = salt.utils.http.query(
            url,
            "GET",
            decode=False,
            text=True,
        )

        keys = salt.utils.json.loads(result["text"])

        ret[user] = {}
        for key in keys:
            if key_ids:
                if str(key["id"]) in key_ids:
                    ret[user][key["id"]] = key["key"]
            else:
                ret[user][key["id"]] = key["key"]

    return ret
