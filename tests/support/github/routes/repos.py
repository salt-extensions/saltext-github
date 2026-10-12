"""
Routes: repositories.
"""

from tests.support.github.base import APIBase
from tests.support.github.entities import Organization
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import PATCH
from tests.support.github.routing import POST


class RepoRoutes(APIBase):
    @GET("orgs/<org>/repos")
    def _list_repos(self, match, _query, _body):
        org = self._resolve_org(match)
        return 200, [repo.payload() for repo in sorted(org.repos, key=lambda x: x.name)]

    @POST("orgs/<org>/repos")
    def _create_repo(self, match, _query, body):
        org = self._resolve_org(match)
        name = body["name"]
        repo_params = {"private": bool(body.get("private"))}
        for fld in ("description", "homepage", "has_issues", "has_wiki", "has_downloads"):
            if fld in body:
                repo_params[fld] = body[fld]
        repo = org.add_repo(name, **repo_params)
        return 201, repo.payload()

    @GET("repos/<org>/<repo>")
    def _get_repo(self, match, _query, _body):
        org = self._resolve_org(match)
        return 200, org.get_repo(match["repo"]).payload()

    @PATCH("repos/<org>/<repo>")
    def _edit_repo(self, match, _query, body):
        repo = self._resolve_repo(match)
        upd = {}
        for fld, value in body.items():
            if fld != "name":
                upd[fld] = value
        return 200, repo.update(**upd).payload()

    @DELETE("repos/<org>/<repo>")
    def _delete_repo(self, match, _query, _body):
        org = self._resolve_org(match)
        org.remove_repo(match["repo"])
        return 204

    @GET("repos/<org>/<repo>/teams")
    def _repo_teams(self, match, _query, _body):
        repo = self._resolve_repo(match)
        owner = repo.owner
        if not isinstance(owner, Organization):
            raise NotImplementedError
        return 200, [
            team.payload()
            for team in sorted(repo.owner.teams, key=lambda x: x.id)
            if repo.data.repo_id in team.data.repos
        ]
