"""
Routes: organization, users, members.
"""

from tests.support.github.base import APIBase
from tests.support.github.entities import NotFound
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import PUT


class OrgRoutes(APIBase):
    @GET("orgs/<org>")
    def _get_org(self, match, _query, _body):
        org = self._resolve_org(match)
        return 200, org.payload()

    @GET("users/<login>")
    def _get_user(self, match, _query, _body):
        # Like the real endpoint, this also resolves organizations
        # (distinguished via the payload's "type" field).
        try:
            return 200, self.state.get_user(match["login"]).payload()
        except NotFound:
            return 200, self.state.get_org(match["login"]).payload()

    @GET("users/<login>/keys")
    def _list_user_keys(self, match, _query, _body):
        return 200, self.state.get_user(match["login"]).key_payloads()

    @GET("orgs/<org>/members")
    def _list_members(self, match, query, _body):
        org = self._resolve_org(match)
        users = [member.user for member in org.active_members()]
        if query.get("filter") == "2fa_disabled":
            users = [user for user in users if not user.two_factor_authentication]
        return 200, [user.payload() for user in users]

    @GET("orgs/<org>/members/<login>")
    def _is_member(self, match, _query, _body):
        org = self._resolve_org(match)
        if org.get_member(match["login"]).state == "active":
            return 204
        raise NotFound(match["login"])

    @DELETE("orgs/<org>/members/<login>")
    def _remove_member(self, match, _query, _body):
        org = self._resolve_org(match)
        login = match["login"]
        org.remove_member(login)
        return 204

    @GET("orgs/<org>/memberships/<login>")
    def _get_membership(self, match, _query, _body):
        org = self._resolve_org(match)
        return 200, org.get_member(match["login"]).payload()

    @PUT("orgs/<org>/memberships/<login>")
    def _put_membership(self, match, _query, _body):
        org = self._resolve_org(match)
        login = match["login"]
        member = org.add_member(login, state="pending")
        return 200, member.payload()
