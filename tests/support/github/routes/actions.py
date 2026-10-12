"""
Routes: Actions secrets and workflow permissions.
"""

import base64

from nacl.public import SealedBox

from tests.support.github.base import APIBase
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import PUT

# The generic secret name pattern must not swallow the public-key route
SECRET_PATH = (
    r"/repos/(?P<org>[^/]+)/(?P<repo>[^/]+)/actions/secrets/(?P<name>(?!public-key$)[^/]+)"
)


class ActionsRoutes(APIBase):
    @GET("repos/<owner>/<repo>/actions/secrets/public-key")
    def _secrets_public_key(self, match, _query, _body):
        self._resolve_repo(match)
        public_key = base64.b64encode(bytes(self.secrets_private_key.public_key)).decode()
        return 200, {"key_id": "568250167242549743", "key": public_key}

    @GET("repos/<owner>/<repo>/actions/secrets")
    def _list_secrets(self, match, _query, _body):
        repo = self._resolve_repo(match)
        secrets = [secret.payload() for secret in sorted(repo.secrets, key=lambda x: x.name)]
        return 200, {"total_count": len(secrets), "secrets": secrets}

    @GET(SECRET_PATH)
    def _get_secret(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, repo.get_secret(match["name"]).payload()

    @PUT(SECRET_PATH)
    def _put_secret(self, match, _query, body):
        repo = self._resolve_repo(match)
        # Decrypt the sealed box to prove the client encrypted correctly
        # (and to allow asserting submitted values in tests).
        value = (
            SealedBox(self.secrets_private_key)
            .decrypt(base64.b64decode(body["encrypted_value"]))
            .decode()
        )
        try:
            secret = repo.get_secret(match["name"])
        except KeyError:
            repo.add_secret(match["name"], value)
            return 201
        secret.update(value=value, updated_at="2026-10-12T00:00:00Z")
        return 204

    @DELETE(SECRET_PATH)
    def _delete_secret(self, match, _query, _body):
        repo = self._resolve_repo(match)
        repo.remove_secret(match["name"])
        return 204

    @GET("repos/<owner>/<repo>/actions/permissions/workflow")
    def _get_workflow_permissions(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, {
            "default_workflow_permissions": repo.data.default_workflow_permissions,
            "can_approve_pull_request_reviews": repo.data.can_approve_pull_request_reviews,
        }

    @PUT("repos/<owner>/<repo>/actions/permissions/workflow")
    def _set_workflow_permissions(self, match, _query, body):
        repo = self._resolve_repo(match)
        upd = {
            fld: body[fld]
            for fld in ("default_workflow_permissions", "can_approve_pull_request_reviews")
            if fld in body
        }
        repo.update(**upd)
        return 204
