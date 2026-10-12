"""
Routes: repository deploy keys.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import POST


class DeployKeyRoutes(APIBase):
    @GET("repos/<owner>/<repo>/keys")
    def _list_deploy_keys(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, [key.payload() for key in sorted(repo.deploy_keys, key=lambda x: x.id)]

    @POST("repos/<owner>/<repo>/keys")
    def _create_deploy_key(self, match, _query, body):
        repo = self._resolve_repo(match)
        key = repo.add_deploy_key(body["title"], body["key"], read_only=bool(body.get("read_only")))
        return 201, key.payload()

    @GET("repos/<owner>/<repo>/keys/<key_id>")
    def _get_deploy_key(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, repo.get_deploy_key(match["key_id"]).payload()

    @DELETE("repos/<owner>/<repo>/keys/<key_id>")
    def _delete_deploy_key(self, match, _query, _body):
        repo = self._resolve_repo(match)
        repo.remove_deploy_key(match["key_id"])
        return 204
