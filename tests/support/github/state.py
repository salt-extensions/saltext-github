"""
Global dict-backed store of the fake GitHub API.
"""

# pyright: reportImportCycles=false  (type-only cycle with .entities, see there)

from collections import defaultdict
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields

from tests.support.github.entities import DeployKey
from tests.support.github.entities import DeployKeyData
from tests.support.github.entities import Entity
from tests.support.github.entities import EntityData
from tests.support.github.entities import Environment
from tests.support.github.entities import EnvironmentData
from tests.support.github.entities import Issue
from tests.support.github.entities import IssueData
from tests.support.github.entities import Label
from tests.support.github.entities import LabelData
from tests.support.github.entities import Member
from tests.support.github.entities import MemberData
from tests.support.github.entities import Milestone
from tests.support.github.entities import MilestoneData
from tests.support.github.entities import NotFound
from tests.support.github.entities import Organization
from tests.support.github.entities import OrganizationData
from tests.support.github.entities import OrgName
from tests.support.github.entities import OrgRulesetData
from tests.support.github.entities import Pages
from tests.support.github.entities import PagesData
from tests.support.github.entities import PullRequest
from tests.support.github.entities import PullRequestData
from tests.support.github.entities import Repo
from tests.support.github.entities import RepoData
from tests.support.github.entities import RepoId
from tests.support.github.entities import RepoRulesetData
from tests.support.github.entities import Ruleset
from tests.support.github.entities import Secret
from tests.support.github.entities import SecretData
from tests.support.github.entities import Team
from tests.support.github.entities import TeamData
from tests.support.github.entities import TeamName
from tests.support.github.entities import User
from tests.support.github.entities import UserData
from tests.support.github.entities import UserName


@dataclass
class GlobalState:  # pylint: disable=too-many-instance-attributes
    base_url: str = field(init=False, default="")
    orgs: dict[OrgName, OrganizationData] = field(default_factory=dict)
    users: dict[UserName, UserData] = field(default_factory=dict)
    repos: dict[RepoId, RepoData] = field(default_factory=dict)
    members: dict[tuple[OrgName, UserName], MemberData] = field(default_factory=dict)
    teams: dict[tuple[OrgName, TeamName], TeamData] = field(default_factory=dict)
    rulesets_org: dict[OrgName, dict[int, OrgRulesetData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    rulesets_repo: dict[RepoId, dict[int, RepoRulesetData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    milestones: dict[RepoId, dict[int, MilestoneData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    issues: dict[RepoId, dict[int, IssueData]] = field(default_factory=lambda: defaultdict(dict))
    pulls: dict[RepoId, dict[int, PullRequestData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    deploy_keys: dict[RepoId, dict[int, DeployKeyData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    secrets: dict[RepoId, dict[str, SecretData]] = field(default_factory=lambda: defaultdict(dict))
    environments: dict[RepoId, dict[str, EnvironmentData]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    labels: dict[RepoId, dict[str, LabelData]] = field(default_factory=lambda: defaultdict(dict))
    pages: dict[RepoId, PagesData] = field(default_factory=dict)

    def __post_init__(self):
        self.snapshot()

    def _stores(self):
        return [fld.name for fld in fields(self) if fld.name != "base_url"]

    def snapshot(self):
        self._snapshot = {name: deepcopy(getattr(self, name)) for name in self._stores()}

    def reset(self):
        for fld in fields(self):
            if fld.name != "base_url":
                setattr(self, fld.name, fld.default_factory())
        self.snapshot()

    def restore(self):
        for name, value in self._snapshot.items():
            setattr(self, name, deepcopy(value))

    def _next_issue_number(self, repo_id: RepoId) -> int:
        # Issues and pull requests share one number sequence per repo.
        return len(self.issues[repo_id]) + len(self.pulls[repo_id]) + 1

    def add_user(self, name: str, **params) -> User:
        user = UserData(name, **params)
        if user.login in self.users:
            raise RuntimeError(f"User {user.login} already exists")
        self.users[user.login] = user
        return User(self, user)

    def add_org(self, name: str, **params) -> Organization:
        org = OrganizationData(name, **params)
        if org.login in self.orgs:
            raise RuntimeError(f"Organization {org.login} already exists")
        self.orgs[org.login] = org
        return Organization(self, org)

    def get_user(self, login: str, *, exc=NotFound) -> User:
        if login not in self.users:
            raise exc(f"Requested nonexistent user {login=}")
        return User(self, self.users[login])

    def get_org(self, login: str, *, exc=NotFound) -> Organization:
        if login not in self.orgs:
            raise exc(f"Requested nonexistent org {login=}")
        return Organization(self, self.orgs[login])

    def get_org_id(self, org_id: int | str, *, exc=NotFound) -> Organization:
        org_id = int(org_id)
        res = next((org for org in self.orgs.values() if org.id == org_id), None)
        if res is None:
            raise exc(f"Requested nonexistent org_id {org_id=}")
        return Organization(self, res)

    def get_repo(self, repo_id: RepoId | Sequence[str] | str, *, exc=NotFound) -> Repo:
        if isinstance(repo_id, RepoId):
            resolved = repo_id
        elif isinstance(repo_id, str):
            resolved = RepoId.from_str(repo_id)
        else:
            resolved = RepoId.from_seq(repo_id)

        if resolved.owner not in self.orgs and resolved.owner not in self.users:
            raise exc(f"Requested repo from nonexistent owner {resolved.owner=}")
        if resolved not in self.repos:
            raise exc(f"Requested nonexistent repo {resolved.name=} from owner {resolved.owner=}")
        return Repo(self, self.repos[resolved])

    def remove_repo(self, repo_id: RepoId | Sequence[str] | str, *, exc=NotFound) -> None:
        repo = self.get_repo(repo_id, exc=exc)
        resolved = repo.data.repo_id
        self.repos.pop(resolved)
        if repo.data.owner_type == "org":
            for team in self.get_org(resolved.owner).teams:
                team.data.repos.pop(resolved, None)
        for store in (
            self.rulesets_repo,
            self.milestones,
            self.issues,
            self.pulls,
            self.deploy_keys,
            self.secrets,
            self.environments,
            self.labels,
        ):
            store.pop(resolved, None)
        self.pages.pop(resolved, None)

    def add(self, entity: EntityData | Entity):
        data = entity.data if isinstance(entity, Entity) else entity

        # Auto-numbering for issue-like entities
        if isinstance(data, MilestoneData) and data.number < 0:
            data = data.with_(number=len(self.milestones[data.repo]) + 1)
        elif isinstance(data, (IssueData, PullRequestData)) and data.number < 0:
            data = data.with_(number=self._next_issue_number(data.repo))

        spec = _STORES.get(type(data))
        if spec is None:
            raise TypeError(f"Unknown object: {data=}")
        entity_cls, store_name, outer_key, inner_key, parent_store = spec
        if parent_store is not None:
            assert outer_key(data) in getattr(self, parent_store)
        store = getattr(self, store_name)
        if inner_key is None:
            store[outer_key(data)] = data
        else:
            store[outer_key(data)][inner_key(data)] = data
        return entity_cls(self, data)

    def replace(self, old: EntityData | Entity, new: EntityData | Entity):
        old_data = old.data if isinstance(old, Entity) else old
        new_data = new.data if isinstance(new, Entity) else new
        assert type(old_data) is type(new_data)
        spec = _STORES.get(type(old_data))
        if spec is None:
            raise TypeError(f"Unknown object: {old_data=}")
        _, store_name, outer_key, inner_key, _ = spec
        store = getattr(self, store_name)
        if inner_key is None:
            store.pop(outer_key(old_data))
        else:
            store[outer_key(old_data)].pop(inner_key(old_data))
        return self.add(new_data)


# EntityData type -> (entity class, store attribute, outer key, inner key,
# store the outer key must exist in). Two-level stores are scoped by the
# outer key, flat ones use it directly.
_STORES = {
    OrganizationData: (Organization, "orgs", lambda d: d.login, None, None),
    UserData: (User, "users", lambda d: d.login, None, None),
    RepoData: (Repo, "repos", lambda d: d.repo_id, None, None),
    MemberData: (Member, "members", lambda d: (d.org, d.login), None, None),
    TeamData: (Team, "teams", lambda d: (d.org, d.slug), None, None),
    OrgRulesetData: (Ruleset, "rulesets_org", lambda d: d.source, lambda d: d.id, "orgs"),
    RepoRulesetData: (Ruleset, "rulesets_repo", lambda d: d.source, lambda d: d.id, "repos"),
    MilestoneData: (Milestone, "milestones", lambda d: d.repo, lambda d: d.number, "repos"),
    IssueData: (Issue, "issues", lambda d: d.repo, lambda d: d.number, "repos"),
    PullRequestData: (PullRequest, "pulls", lambda d: d.repo, lambda d: d.number, "repos"),
    DeployKeyData: (DeployKey, "deploy_keys", lambda d: d.repo, lambda d: d.id, "repos"),
    SecretData: (Secret, "secrets", lambda d: d.repo, lambda d: d.name, "repos"),
    EnvironmentData: (Environment, "environments", lambda d: d.repo, lambda d: d.name, "repos"),
    LabelData: (Label, "labels", lambda d: d.repo, lambda d: d.name, "repos"),
    PagesData: (Pages, "pages", lambda d: d.repo, None, "repos"),
}
