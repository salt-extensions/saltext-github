"""
Routes: issues, issue comments and pull requests.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import GET


def _state_matches(entity_state, query):
    wanted = query.get("state", "open")
    return wanted in {"all", entity_state}


class IssueRoutes(APIBase):
    @GET(r"/repos/<org>/<repo>/issues")
    def _list_issues(self, match, query, _body):
        repo = self._resolve_repo(match)
        wanted_labels = set(filter(None, query.get("labels", "").split(",")))
        rend = []
        for issue in sorted(repo.issues, key=lambda x: x.number):
            if not _state_matches(issue.state, query):
                continue
            if wanted_labels and not wanted_labels.issubset(issue.labels):
                continue
            rend.append(issue.payload())
        # The issues list includes pull requests, marked with a pull_request key.
        if not wanted_labels:
            for pull in sorted(repo.pulls, key=lambda x: x.number):
                if _state_matches(pull.state, query):
                    rend.append(pull.issue_payload())
        return 200, rend

    @GET(r"/repos/<org>/<repo>/issues/<number>")
    def _get_issue(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, repo.get_issue(match["number"]).payload()

    @GET(r"/repos/<org>/<repo>/issues/<number>/comments")
    def _list_issue_comments(self, match, query, _body):
        repo = self._resolve_repo(match)
        issue = repo.get_issue(match["number"])
        since = query.get("since")
        return 200, [
            comment.payload()
            for comment in sorted(issue.comment_list, key=lambda x: x.created_at)
            if since is None or comment.updated_at >= since
        ]

    @GET(r"/repos/<org>/<repo>/pulls")
    def _list_pulls(self, match, query, _body):
        repo = self._resolve_repo(match)
        return 200, [
            pull.payload()
            for pull in sorted(repo.pulls, key=lambda x: x.number)
            if _state_matches(pull.state, query)
        ]
