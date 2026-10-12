"""
Routes: repository (issue) labels.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import PATCH
from tests.support.github.routing import POST


class LabelRoutes(APIBase):
    @GET("repos/<owner>/<repo>/labels")
    def _list_labels(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, [label.payload() for label in sorted(repo.labels, key=lambda x: x.name)]

    @POST("repos/<owner>/<repo>/labels")
    def _create_label(self, match, _query, body):
        repo = self._resolve_repo(match)
        assert body["name"] not in repo.labels
        params = {fld: body[fld] for fld in ("color", "description") if fld in body}
        label = repo.add_label(body["name"], **params)
        return 201, label.payload()

    @GET("repos/<owner>/<repo>/labels/<name>")
    def _get_label(self, match, _query, _body):
        repo = self._resolve_repo(match)
        return 200, repo.get_label(match["name"]).payload()

    @PATCH("repos/<owner>/<repo>/labels/<name>")
    def _edit_label(self, match, _query, body):
        repo = self._resolve_repo(match)
        label = repo.get_label(match["name"])
        upd = {fld: body[fld] for fld in ("color", "description") if fld in body}
        if "new_name" in body:
            upd["name"] = body["new_name"]
        return 200, label.update(**upd).payload()

    @DELETE("repos/<owner>/<repo>/labels/<name>")
    def _delete_label(self, match, _query, _body):
        repo = self._resolve_repo(match)
        repo.remove_label(match["name"])
        return 204
