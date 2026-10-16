"""
Routes: GitHub App installations. These endpoints require app (JWT)
authentication, which dispatch enforces (see ``APP_JWT_ROUTES``).
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import POST


class AppRoutes(APIBase):
    def _installation(self, login, target_type):
        for owner, installation_id in self.app_installations.items():
            if owner.lower() == login.lower():
                return {
                    "id": installation_id,
                    "app_id": self.app_id,
                    "target_type": target_type,
                    "account": {"login": login, "type": target_type},
                }
        raise KeyError(f"App {self.app_id} is not installed on {login}")

    @GET("orgs/<org>/installation")
    def _org_installation(self, match, _query, _body):
        org = self._resolve_org(match)
        return 200, self._installation(org.data.login, "Organization")

    @GET("users/<username>/installation")
    def _user_installation(self, match, _query, _body):
        user = self.state.get_user(match["username"])
        return 200, self._installation(user.data.login, "User")

    @POST("app/installations/<installation_id>/access_tokens")
    def _create_installation_token(self, match, _query, body):
        installation_id = int(match["installation_id"])
        for account, account_install_id in self.app_installations.items():
            if account_install_id == installation_id:
                break
        else:
            raise KeyError(f"No app installation with ID {installation_id}")
        token = self._get_app_token(account, (body or {}).get("permissions"))
        token_meta = self.app_tokens[token]
        return 201, {
            "token": token,
            "expires_at": token_meta["expires_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            # Unrestricted tokens carry the app's granted permissions,
            # which this fake does not model in detail
            "permissions": token_meta["permissions"].copy(),
            "repository_selection": "all",
        }

    @DELETE("installation/token")
    def _revoke_installation_token(self, _match, _query, _body):
        # Actual revocation is handled in the base class dispatch method,
        # this path is only hit when the token does not exist
        return 404
