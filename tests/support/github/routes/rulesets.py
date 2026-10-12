"""
Routes: rulesets (repo- and org-scoped).
"""

from tests.support.github.base import APIBase
from tests.support.github.entities import Ruleset
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import POST
from tests.support.github.routing import PUT


class RulesetRoutes(APIBase):
    def _get_ruleset(self, match) -> Ruleset:
        if "repo" in match.groupdict():
            repo = self._resolve_repo(match)
            return repo.get_ruleset(match["ruleset_id"])
        org = self._resolve_org(match)
        return org.get_ruleset(match["ruleset_id"])

    @GET("repos/<org>/<repo>/rulesets")
    def _list_repo_rulesets(self, match, query, body):
        repo = self._resolve_repo(match)
        rulesets = [ruleset.payload() for ruleset in repo.rulesets]
        return 200, rulesets

    @GET("orgs/<org>/rulesets")
    def _list_org_rulesets(self, match, query, body):
        org = self._resolve_org(match)
        rulesets = [ruleset.payload() for ruleset in org.rulesets]
        return 200, rulesets

    @POST("repos/<org>/<repo>/rulesets")
    def _add_repo_ruleset(self, match, query, body):
        repo = self._resolve_repo(match)
        ruleset = repo.add_ruleset(**dict(body))
        return 201, ruleset.payload()

    @POST("orgs/<org>/rulesets")
    def _add_org_ruleset(self, match, query, body):
        org = self._resolve_org(match)
        ruleset = org.add_ruleset(**dict(body))
        return 201, ruleset.payload()

    @GET("repos/<org>/<repo>/rulesets/<ruleset_id>")
    def _get_repo_ruleset(self, match, query, body):
        ruleset = self._get_ruleset(match)
        return 200, ruleset.payload()

    @GET("orgs/<org>/rulesets/<ruleset_id>")
    def _get_org_ruleset(self, match, query, body):
        ruleset = self._get_ruleset(match)
        return 200, ruleset.payload()

    @PUT("repos/<org>/<repo>/rulesets/<ruleset_id>")
    def _update_repo_ruleset(self, match, query, body):
        ruleset = self._get_ruleset(match)
        return 200, ruleset.update(**body).payload()

    @PUT("orgs/<org>/rulesets/<ruleset_id>")
    def _update_org_ruleset(self, match, query, body):
        ruleset = self._get_ruleset(match)
        return 200, ruleset.update(**body).payload()

    @DELETE("repos/<org>/<repo>/rulesets/<ruleset_id>")
    def _delete_repo_ruleset(self, match, query, body):
        repo = self._resolve_repo(match)
        repo.remove_ruleset(match["ruleset_id"])
        return 204

    @DELETE("orgs/<org>/rulesets/<ruleset_id>")
    def _delete_org_ruleset(self, match, query, body):
        org = self._resolve_org(match)
        org.remove_ruleset(match["ruleset_id"])
        return 204
