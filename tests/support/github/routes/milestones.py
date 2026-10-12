"""
Routes: milestones.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import GET


class MilestoneRoutes(APIBase):
    @GET("repos/<org>/<repo>/milestones")
    def _list_milestones(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, [milestone.payload() for milestone in repo.milestones]

    @GET("repos/<org>/<repo>/milestones/<number>")
    def _get_milestone(self, match, _query, _body):
        repo = self._resolve_repo(match)
        milestone = repo.get_milestone(match["number"])
        return 200, milestone.payload()
