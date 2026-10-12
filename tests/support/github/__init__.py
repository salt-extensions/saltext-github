"""
A stateful fake GitHub API server for functional tests.

The server implements the subset of the GitHub REST API that this extension
consumes, backed by plain dicts. It allows exercising the execution and state
modules end-to-end (idempotence, drift detection, test mode) without network
access or mocking individual functions.

Layout:

:mod:`~tests.support.github.entities`
    Typed entity model (``*Data`` storage dataclasses + hydrated wrappers),
    ``EntityView``, ``NotFound``.
:mod:`~tests.support.github.state`
    ``GlobalState`` — the dict-backed store with snapshot/restore.
:mod:`~tests.support.github.routing`
    Route declaration decorators (``GET``/``POST``/...) and ``Request``.
:mod:`~tests.support.github.base`
    ``APIBase`` — dispatch, shared resolvers, request log, HTTP plumbing.
:mod:`~tests.support.github.routes`
    Per-area route mixins composed into :class:`FakeGitHubAPI` below.
"""

from tests.support.github.base import ORG
from tests.support.github.base import TOKEN
from tests.support.github.entities import Entity
from tests.support.github.entities import EntityData
from tests.support.github.entities import EntityView
from tests.support.github.entities import Issue
from tests.support.github.entities import IssueComment
from tests.support.github.entities import Member
from tests.support.github.entities import Milestone
from tests.support.github.entities import NotFound
from tests.support.github.entities import Organization
from tests.support.github.entities import PullRequest
from tests.support.github.entities import Repo
from tests.support.github.entities import RepoId
from tests.support.github.entities import Ruleset
from tests.support.github.entities import Team
from tests.support.github.entities import TeamMember
from tests.support.github.entities import User
from tests.support.github.routes import IssueRoutes
from tests.support.github.routes import MilestoneRoutes
from tests.support.github.routes import OrgRoutes
from tests.support.github.routes import RepoRoutes
from tests.support.github.routes import RulesetRoutes
from tests.support.github.routes import TeamRoutes
from tests.support.github.routing import Request
from tests.support.github.state import GlobalState

__all__ = [
    "ORG",
    "TOKEN",
    "Entity",
    "EntityData",
    "EntityView",
    "FakeGitHubAPI",
    "GlobalState",
    "Issue",
    "IssueComment",
    "Member",
    "Milestone",
    "NotFound",
    "Organization",
    "PullRequest",
    "Repo",
    "RepoId",
    "Request",
    "Ruleset",
    "Team",
    "TeamMember",
    "User",
]


class FakeGitHubAPI(OrgRoutes, RepoRoutes, TeamRoutes, RulesetRoutes, MilestoneRoutes, IssueRoutes):
    """
    Dict-backed implementation of the consumed GitHub API surface.
    """
