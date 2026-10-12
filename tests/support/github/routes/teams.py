"""
Routes: teams, including legacy by-ID paths.
"""

import re

from tests.support.github.base import APIBase
from tests.support.github.entities import NotFound
from tests.support.github.entities import OrgName
from tests.support.github.entities import RepoId
from tests.support.github.entities import Team
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import PATCH
from tests.support.github.routing import POST
from tests.support.github.routing import PUT


def _team_uris(resource=""):
    """
    Render the three URI flavors (modern by slug, modern by ID, legacy by ID)
    of a team resource. Repos are addressed by full name in all flavors.
    """
    resource = resource.replace("<repo>", "<owner>/<repo>")
    modern_slug = f"orgs/<org>/teams/<team_slug>/{resource}".rstrip("/")
    modern_id = f"organizations/<org_id>/team/<team_id>/{resource}".rstrip("/")
    legacy = f"teams/<team_id>/{resource}".rstrip("/")
    return modern_slug, modern_id, legacy


class TeamRoutes(APIBase):
    def _team_by_id(self, team_id: int | str, org: OrgName | None = None) -> Team:
        team_id = int(team_id)
        for team_key, team in self.state.teams.items():
            if org is not None and team_key[0] != org:
                continue
            if team.id == team_id:
                return Team(self.state, team)
        raise NotFound(team_id)

    def _resolve_team(self, match: re.Match) -> Team:
        # This is from a route, where NotFound exceptions indicate 404
        dic = match.groupdict()
        org = ret = org_login = None
        if "org_id" in dic or "org" in dic:
            org = self._resolve_org(match)
            org_login = org.data.login
        if "team_id" in dic:
            team_id = int(dic["team_id"])
            ret = self._team_by_id(team_id, org_login)
        if "team_slug" in dic:
            assert org
            ret = org.get_team(dic["team_slug"])
        if ret is not None:
            return ret
        raise TypeError("Missing team_id or team_slug in match")

    @GET("orgs/<org>/teams")
    def _list_teams(self, match, query, body):
        org = self._resolve_org(match)
        return 200, [team.payload() for team in sorted(org.teams, key=lambda x: x.id)]

    @POST("orgs/<org>/teams")
    def _create_team(self, match, query, body):
        org = self._resolve_org(match)
        if "privacy" not in body:
            body["privacy"] = "secret"
        for name in body.pop("repo_names", []):
            # The real API expects full names, but tolerate bare ones (same org).
            repo_id = RepoId.from_str(name) if "/" in name else RepoId(org.data.login, name)
            self.state.get_repo(repo_id, exc=ValueError)
            body.setdefault("repos", {})[repo_id] = "pull"
        team = org.add_team(**body)
        return 201, team.payload()

    @GET(*_team_uris())
    def _get_team(self, match, query, body):
        return 200, self._resolve_team(match).payload()

    @PATCH(*_team_uris())
    def _edit_team(self, match, query, body):
        team = self._resolve_team(match)
        new_team = team.update(
            **{
                fld: body[fld]
                for fld in ("name", "description", "privacy", "permission")
                if body.get(fld) is not None
            }
        )
        return 200, new_team.payload()

    @DELETE(*_team_uris())
    def _delete_team(self, match, query, body):
        team = self._resolve_team(match)
        team.org.remove_team(team.slug)
        return 204

    @GET(*_team_uris("repos"))
    def _team_repos(self, match, query, body):
        team = self._resolve_team(match)
        return 200, [
            self.state.get_repo(repo_id).team_payload(permission)
            for repo_id, permission in sorted(team.repos.items())
        ]

    @PUT(*_team_uris("repos/<repo>"))
    def _team_add_repo(self, match, query, body):
        team = self._resolve_team(match)
        repo = self.state.get_repo((match["owner"], match["repo"]))
        team.add_repo(repo, (body or {}).get("permission", "pull"))
        return 204

    @DELETE(*_team_uris("repos/<repo>"))
    def _team_remove_repo(self, match, query, body):
        team = self._resolve_team(match)
        repo = self.state.get_repo((match["owner"], match["repo"]))
        team.remove_repo(repo)
        return 204

    @GET(*_team_uris("members"))
    def _team_members(self, match, query, body):
        team = self._resolve_team(match)
        return 200, [
            member.user.payload() for member in sorted(team.members, key=lambda x: x.data.login)
        ]

    @GET("teams/<team_id>/members/<login>")
    def _team_is_member(self, match, query, body):
        # legacy only
        team = self._resolve_team(match)
        login = match["login"]
        if login in team.data.members:
            return 204
        raise NotFound(login)

    @GET(*_team_uris("memberships/<login>"))
    def _team_get_member(self, match, query, body):
        team = self._resolve_team(match)
        login = match["login"]
        if login in team.data.members:
            return 204
        raise NotFound(login)

    @DELETE(
        "orgs/<org>/teams/<team_slug>/memberships/<login>",
        "teams/<team_id>/memberships/<login>",
    )
    def _delete_membership(self, match, query, body):
        team = self._resolve_team(match)
        team.remove_member(match["login"])
        return 204

    @DELETE(*_team_uris("members/<login>"))
    def _team_remove_member_legacy(self, match, query, body):
        team = self._resolve_team(match)
        team.remove_member(match["login"])
        return 204

    @PUT(*_team_uris("memberships/<login>"))
    def _team_add_member(self, match, query, body):
        team = self._resolve_team(match)
        membership = team.add_member(match["login"])
        return 200, membership.payload()
