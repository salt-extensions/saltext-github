"""
Exceptions raised by the GitHub API helper modules.
"""

from salt.exceptions import CommandExecutionError


class GitHubApiError(CommandExecutionError):
    """
    The GitHub API returned an error response.

    status
        The HTTP status code of the response, if available.

    data
        The decoded response body, if available.
    """

    def __init__(self, message, *, status=None, data=None):
        super().__init__(message)
        self.status = status
        self.data = data


class GitHubNotFoundError(GitHubApiError):
    """
    A requested GitHub resource does not exist.
    """
