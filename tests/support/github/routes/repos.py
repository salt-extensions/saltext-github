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
    @staticmethod
    def _creation_params(body):
        repo_params = {"private": bool(body.get("private"))}
        for fld in ("description", "homepage", "has_issues", "has_wiki", "has_downloads"):
            if fld in body:
                repo_params[fld] = body[fld]
        return repo_params

    @GET("orgs/<org>/repos")
    def _list_repos(self, match, _query, _body):
        org = self._resolve_org(match)
        return 200, [repo.payload() for repo in sorted(org.repos, key=lambda x: x.name)]

    @POST("orgs/<org>/repos")
    def _create_repo(self, match, _query, body):
        org = self._resolve_org(match)
        repo = org.add_repo(body["name"], **self._creation_params(body))
        return 201, repo.payload()

    @GET("users/<login>/repos")
    def _list_user_repos(self, match, _query, _body):
        user = self.state.get_user(match["login"])
        # Like the real API, this endpoint only lists public repositories.
        return 200, [
            repo.payload() for repo in sorted(user.repos, key=lambda x: x.name) if not repo.private
        ]

    @GET("user")
    def _get_auth_user(self, _match, _query, _body):
        return 200, self.state.get_user(self.auth_login).payload()

    @GET("user/repos")
    def _list_auth_user_repos(self, _match, _query, _body):
        user = self.state.get_user(self.auth_login)
        return 200, [repo.payload() for repo in sorted(user.repos, key=lambda x: x.name)]

    @POST("user/repos")
    def _create_auth_user_repo(self, _match, _query, body):
        user = self.state.get_user(self.auth_login)
        repo = user.add_repo(body["name"], **self._creation_params(body))
        return 201, repo.payload()

    @GET("repos/<owner>/<repo>")
    def _get_repo(self, match, _query, _body):
        return 200, self._resolve_repo(match).payload()

    @PATCH("repos/<owner>/<repo>")
    def _edit_repo(self, match, _query, body):
        repo = self._resolve_repo(match)
        upd = {}
        for fld, value in body.items():
            if fld != "name":
                upd[fld] = value
        return 200, repo.update(**upd).payload()

    @DELETE("repos/<owner>/<repo>")
    def _delete_repo(self, match, _query, _body):
        repo = self._resolve_repo(match)
        self.state.remove_repo(repo.data.repo_id)
        return 204

    @GET("repos/<owner>/<repo>/teams")
    def _repo_teams(self, match, _query, _body):
        repo = self._resolve_repo(match)
        owner = repo.owner
        if not isinstance(owner, Organization):
            # Teams are organization entities, user-owned repos have none.
            return 200, []
        return 200, [
            team.payload()
            for team in sorted(owner.teams, key=lambda x: x.id)
            if repo.data.repo_id in team.data.repos
        ]
