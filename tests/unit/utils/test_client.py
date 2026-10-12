from unittest.mock import MagicMock

import github as pygithub
import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import client as gh_client
from saltext.github.utils.gh.exceptions import GitHubApiError
from saltext.github.utils.gh.exceptions import GitHubNotFoundError


@pytest.fixture
def requester():
    return MagicMock()


@pytest.fixture
def conn(requester):
    return MagicMock(client=MagicMock(requester=requester))


def test_query_decodes_json_string_data(conn, requester):
    requester.requestJson.return_value = (200, {}, '{"written": true}')

    ret = gh_client.query(conn, "repos", method="POST", data='{"some": "payload"}')

    assert ret == {"written": True}
    requester.requestJson.assert_called_once_with(
        "POST", "/repos", parameters=None, headers=None, input={"some": "payload"}
    )


def test_query_merges_paginated_results(conn, requester):
    requester.requestJson.side_effect = (
        (200, {"Link": '<https://example.com/repos?page=2>; rel="next"'}, '[{"id": 1}]'),
        (200, {}, '[{"id": 2}]'),
    )

    ret = gh_client.query(conn, ["repos"])

    assert ret == [{"id": 1}, {"id": 2}]
    assert requester.requestJson.call_args.kwargs["parameters"] == {"page": "2"}


def test_query_github_exception(conn, requester):
    requester.requestJson.side_effect = pygithub.GithubException(502, {"message": "bad gateway"})

    with pytest.raises(GitHubApiError, match="bad gateway") as exc:
        gh_client.query(conn, "repos")

    assert exc.value.status == 502


def test_query_error_response(conn, requester):
    requester.requestJson.return_value = (404, {}, '{"message": "Not Found"}')

    with pytest.raises(GitHubNotFoundError, match="404 Not Found") as exc:
        gh_client.query(conn, "repos")

    assert exc.value.status == 404
    assert exc.value.data == {"message": "Not Found"}


def test_query_unexpected_exception(conn, requester):
    requester.requestJson.side_effect = OSError("connection refused")

    with pytest.raises(CommandExecutionError, match="connection refused"):
        gh_client.query(conn, "repos")


def test_api_request_translates_pygithub_exceptions():
    @gh_client.api_request
    def _not_found():
        raise pygithub.UnknownObjectException(404, {"message": "Not Found"})

    @gh_client.api_request
    def _server_error():
        raise pygithub.GithubException(502, {"message": "bad gateway"})

    with pytest.raises(GitHubNotFoundError, match="404 Not Found") as exc:
        _not_found()
    assert exc.value.status == 404

    with pytest.raises(GitHubApiError, match="502 bad gateway") as exc:
        _server_error()
    assert exc.value.status == 502
