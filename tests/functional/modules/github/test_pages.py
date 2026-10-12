import pytest
from salt.exceptions import CommandExecutionError


def test_get_pages(github):
    ret = github.get_pages(repo_name="repo-b")
    assert ret["build_type"] == "legacy"
    assert ret["source"] == {"branch": "gh-pages", "path": "/"}


def test_get_pages_missing(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.get_pages()  # repo-a has no Pages site


def test_setup_pages(github, fake_org):
    ret = github.setup_pages(build_type="workflow")
    assert ret["build_type"] == "workflow"
    assert fake_org.get_repo("repo-a").pages.build_type == "workflow"


def test_setup_pages_legacy_source(github, fake_org):
    github.setup_pages(build_type="legacy", source_branch="docs", source_path="/docs")
    pages = fake_org.get_repo("repo-a").pages
    assert pages.source == {"branch": "docs", "path": "/docs"}


def test_update_pages(github, fake_org):
    assert github.update_pages(build_type="workflow", repo_name="repo-b") is True
    pages = fake_org.get_repo("repo-b").pages
    assert pages.build_type == "workflow"
    # Unspecified settings are left untouched
    assert pages.source == {"branch": "gh-pages", "path": "/"}


def test_update_pages_https(github, fake_org):
    assert github.update_pages(https_enforced=True, repo_name="repo-b") is True
    assert fake_org.get_repo("repo-b").pages.https_enforced is True


def test_update_pages_missing(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.update_pages(build_type="workflow")


def test_remove_pages(github, fake_org):
    assert github.remove_pages(repo_name="repo-b") is True
    assert fake_org.get_repo("repo-b").pages is None


def test_remove_pages_missing(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.remove_pages()
