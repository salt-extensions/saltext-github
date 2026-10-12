"""
Routes: GitHub Pages sites.
"""

from tests.support.github.base import APIBase
from tests.support.github.routing import DELETE
from tests.support.github.routing import GET
from tests.support.github.routing import POST
from tests.support.github.routing import PUT


class PagesRoutes(APIBase):
    @GET("repos/<owner>/<repo>/pages")
    def _get_pages(self, match, _query, _body):
        repo = self._resolve_repo(match)
        if repo.pages is None:
            return 404, {"message": "Not Found"}
        return 200, repo.pages.payload()

    @POST("repos/<owner>/<repo>/pages")
    def _create_pages(self, match, _query, body):
        repo = self._resolve_repo(match)
        assert repo.pages is None
        params = {fld: body[fld] for fld in ("build_type", "source") if fld in (body or {})}
        params.setdefault("source", {"branch": repo.data.default_branch, "path": "/"})
        pages = repo.set_pages(**params)
        return 201, pages.payload()

    @PUT("repos/<owner>/<repo>/pages")
    def _update_pages(self, match, _query, body):
        repo = self._resolve_repo(match)
        pages = repo.pages
        if pages is None:
            return 404, {"message": "Not Found"}
        upd = {
            fld: body[fld]
            for fld in ("build_type", "source", "cname", "https_enforced")
            if fld in body
        }
        pages.update(**upd)
        return 204

    @DELETE("repos/<owner>/<repo>/pages")
    def _delete_pages(self, match, _query, _body):
        repo = self._resolve_repo(match)
        repo.remove_pages()
        return 204
