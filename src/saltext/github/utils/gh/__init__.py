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

from saltext.github.utils.gh.exceptions import GitHubApiError  # noqa: F401
from saltext.github.utils.gh.exceptions import GitHubNotFoundError  # noqa: F401
