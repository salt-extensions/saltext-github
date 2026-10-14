"""
Routes: repository contents.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import GET


class ContentsRoutes(APIBase):
    # Full regex: file paths contain slashes, which the `<path>`
    # shorthand expansion does not cover.
    @GET(r"/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)/contents/(?P<path>.+)")
    def _get_content(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, repo.get_file(match["path"]).payload()
