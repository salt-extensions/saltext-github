"""
Entity model of the fake GitHub API.

Each entity comes in two flavors: a plain ``*Data`` dataclass holding the
stored state and a hydrated ``Entity`` wrapper that is bound to the
:class:`~tests.support.github.state.GlobalState` and offers navigation,
payload rendering and persistence helpers.

Payload ``url`` fields are rendered with the server's own base URL since
PyGithub asserts that followed URLs stay within the configured API host.
"""

# The type-only entities ⇄ state cycle is intentional: entities are annotated
# with the GlobalState they are bound to, while the state stores entity data.
# pyright: reportImportCycles=false

import zlib
from collections.abc import Callable
from collections.abc import ItemsView
from collections.abc import Iterator
from collections.abc import KeysView
from dataclasses import KW_ONLY
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import Literal
from typing import NamedTuple
from typing import TypeAlias
from typing import TypeVar

if TYPE_CHECKING:
    from tests.support.github.state import GlobalState

CREATED_AT = "2026-10-11T13:37:42Z"

OrgName: TypeAlias = str
RepoName: TypeAlias = str
TeamName: TypeAlias = str
UserName: TypeAlias = str

ActorName: TypeAlias = UserName | OrgName

K = TypeVar("K")
V = TypeVar("V")


class NotFound(KeyError):
    """
    Raised for lookups of entities that don't exist.
    Routes translate it (or any ``KeyError``) into a 404 response.
    """


class RepoId(NamedTuple):
    owner: ActorName
    name: RepoName

    def __str__(self):
        return f"{self.owner}/{self.name}"

    @classmethod
    def from_str(cls, inpt):
        try:
            owner, name = inpt.split("/", maxsplit=1)
        except (AttributeError, ValueError) as err:  # pragma: no cover
            raise TypeError(f"Invalid repo_id: {inpt=}") from err
        return cls(owner, name)

    @classmethod
    def from_seq(cls, inpt):
        try:
            owner, name = inpt
        except (TypeError, ValueError) as err:  # pragma: no cover
            raise TypeError(f"Invalid repo_id: {inpt=}") from err
        return cls(owner, name)


@dataclass
class EntityData:
    """
    Base class for entity data. Autogenerates an ID based on login/name/title attribute
    and exposes a ``with_`` method to create an updated (detached) object.

    IDs are derived via CRC-32 so they are deterministic across test runs
    (``hash()`` is randomized per process). Caveat: renaming an entity hence
    changes its ID, unlike real GitHub.
    """

    id: int = field(init=False, repr=False)

    with_ = replace

    def __post_init__(self):
        for attr in ("login", "name", "title"):
            if key := getattr(self, attr, None):
                self.id = zlib.crc32(f"{type(self).__name__}/{key}".encode())
                return
        raise RuntimeError("Cannot generate ID, missing login, name or title")  # pragma: no cover


@dataclass
class Entity:
    """
    Base class for interactive entities that resolve to hydrated types and expose payloads.
    Wraps ``EntityData``.
    """

    gh: "GlobalState"
    data: EntityData

    def payload(self, /, **ovrr):
        return asdict(self.data) | ovrr

    def with_(self, **upd):
        """
        Return an updated copy. It is detached, i.e. NOT persisted in the
        global state — use ``update`` for that.
        """
        return replace(self, data=self.data.with_(**upd))

    def update(self, **upd):
        """
        Persist an updated version of this entity in the global state
        and return the new entity.
        """
        return self.gh.replace(self, self.with_(**upd))

    def __getattr__(self, key):
        return getattr(self.data, key)


class EntityView(Generic[K, V]):
    """
    Read-only view over a keyed entity collection.

    Iteration yields the collection's *values* (entities or, for team repos,
    permissions), while membership checks and item access accept the natural
    key (login, name, slug, title). Membership checks also accept an entity.
    """

    def __init__(self, items: dict[K, V], resolve: Callable[[Any], K] | None = None):
        self._items = items
        self._resolve = resolve

    def _key(self, key: Any) -> K:
        if self._resolve is not None and key not in self._items:
            return self._resolve(key)
        return key

    def __iter__(self) -> Iterator[V]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, Entity):
            return any(
                key.data is item.data for item in self._items.values() if isinstance(item, Entity)
            )
        try:
            return self._key(key) in self._items
        except TypeError:
            return False

    def __getitem__(self, key: Any) -> V:
        try:
            return self._items[self._key(key)]
        except KeyError:
            raise NotFound(key) from None

    def get(self, key: Any, default: V | None = None) -> V | None:
        try:
            return self[key]
        except (NotFound, TypeError):
            return default

    def keys(self) -> KeysView[K]:
        return self._items.keys()

    def items(self) -> ItemsView[K, V]:
        return self._items.items()

    def __repr__(self):
        return f"{type(self).__name__}({self._items!r})"


@dataclass
class OrganizationData(EntityData):
    name: str
    _: KW_ONLY
    login: OrgName = ""
    company: str = "Example Corp"

    def __post_init__(self):
        if not self.login:
            self.login = self.name.lower().replace(" ", "-")
        super().__post_init__()


@dataclass
class Organization(Entity):
    data: OrganizationData

    def payload(self, /, **ovrr):
        return (
            asdict(self.data)
            | {
                "url": f"{self.gh.base_url}/orgs/{self.data.login}",
                "html_url": f"https://github.example.com/{self.data.login}",
            }
            | ovrr
        )

    @property
    def members(self) -> "EntityView[UserName, Member]":
        org = self.data.login
        return EntityView(
            {
                login: Member(self.gh, member)
                for (org_name, login), member in self.gh.members.items()
                if org_name == org
            }
        )

    @property
    def repos(self) -> "EntityView[RepoName, Repo]":
        org = self.data.login
        return EntityView(
            {
                repo_id.name: Repo(self.gh, repo)
                for repo_id, repo in self.gh.repos.items()
                if repo_id.owner == org
            }
        )

    @property
    def rulesets(self) -> "EntityView[str, Ruleset]":
        return EntityView(
            {
                data.name: Ruleset(self.gh, data)
                for data in self.gh.rulesets_org[self.data.login].values()
            }
        )

    @property
    def teams(self) -> "EntityView[TeamName, Team]":
        org = self.data.login
        return EntityView(
            {
                slug: Team(self.gh, team)
                for (org_name, slug), team in self.gh.teams.items()
                if org_name == org
            }
        )

    def add_repo(self, name: RepoName, **params) -> "Repo":
        repo_id = RepoId(self.data.login, name)
        assert repo_id not in self.gh.repos
        repo = RepoData(name, self.data.login, **params)
        return self.gh.add(repo)

    def get_repo(self, name: RepoName, *, exc=NotFound) -> "Repo":
        return self.gh.get_repo(RepoId(self.data.login, name), exc=exc)

    def remove_repo(self, name: RepoName, *, exc=NotFound) -> None:
        repo_id = RepoId(self.data.login, name)
        if repo_id not in self.gh.repos:
            raise exc(f"Repo {repo_id=} does not exist")
        self.gh.repos.pop(repo_id)
        for team in self.teams:
            team.data.repos.pop(repo_id, None)

    def add_member(self, user: "User | UserData | UserName", *, exc=NotFound, **params) -> "Member":
        login = user if isinstance(user, UserName) else user.login
        if login not in self.gh.users:
            raise exc(f"User {login=} does not exist")
        membership_id = (self.data.login, login)
        if membership_id in self.gh.members:
            return Member(self.gh, self.gh.members[membership_id])
        member = MemberData(login, self.data.login, **params)
        return self.gh.add(member)

    def get_member(self, login: str, *, exc=NotFound) -> "Member":
        member_key = (self.data.login, login)
        if member_key not in self.gh.members:
            raise exc(f"Requested nonexistent member {login=} from org {self.data.login}")
        return Member(self.gh, self.gh.members[member_key])

    def remove_member(self, login: str) -> None:
        member_key = (self.data.login, login)
        self.gh.members.pop(member_key, None)
        for team in self.teams:
            team.data.members.pop(login, None)

    def active_members(self) -> "list[Member]":
        # Pending invitees are not members yet, matching GitHub behavior.
        return [member for member in self.members if member.state == "active"]

    def add_team(self, name: str, **params) -> "Team":
        team = TeamData(name, self.data.login, **params)
        team_key = (self.data.login, team.slug)
        assert team_key not in self.gh.teams
        return self.gh.add(team)

    def get_team(self, slug: str, *, exc=NotFound) -> "Team":
        team_key = (self.data.login, slug)
        if team_key not in self.gh.teams:
            raise exc(f"Requested nonexistent team {slug=} from org {self.data.login}")
        return Team(self.gh, self.gh.teams[team_key])

    def remove_team(self, slug: str, *, exc=NotFound) -> None:
        team_key = (self.data.login, slug)
        if team_key not in self.gh.teams:
            raise exc(f"Team {slug=} does not exist in org {self.data.login}")
        self.gh.teams.pop(team_key)

    def add_ruleset(self, name: str, **params) -> "Ruleset":
        ruleset = OrgRulesetData(name, self.data.login, **params)
        return self.gh.add(ruleset)

    def get_ruleset(self, rs_id: int | str, *, exc=NotFound) -> "Ruleset":
        rs_id = int(rs_id)
        if rs_id not in self.gh.rulesets_org[self.data.login]:
            raise exc(f"Org ruleset with id {rs_id=} does not exist for org {self.data.login=}")
        return Ruleset(self.gh, self.gh.rulesets_org[self.data.login][rs_id])

    def remove_ruleset(self, rs_id: int | str, *, exc=NotFound) -> None:
        rs_id = int(rs_id)
        if rs_id not in self.gh.rulesets_org[self.data.login]:
            raise exc(f"Org ruleset with id {rs_id=} does not exist for org {self.data.login=}")
        del self.gh.rulesets_org[self.data.login][rs_id]


@dataclass
class UserData(EntityData):
    name: str
    _: KW_ONLY
    login: UserName = ""
    email: str = ""
    two_factor_authentication: bool = True
    company: str = "Example Corp"
    type: str = "User"
    created_at: str = CREATED_AT
    updated_at: str = CREATED_AT
    public_repos: int = 2
    public_gists: int = 1
    followers: int = 42
    following: int = 37

    def __post_init__(self):
        if not self.login:
            self.login = self.name.lower().replace(" ", "-")
        if not self.email:
            self.email = f"{self.login}@example.com"
        super().__post_init__()


@dataclass
class User(Entity):
    data: UserData

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        return (
            rend
            | {
                "url": f"{self.gh.base_url}/users/{self.data.login}",
                "html_url": f"https://github.example.com/{self.data.login}",
            }
            | ovrr
        )


@dataclass
class MemberData(EntityData):
    login: UserName
    org: OrgName
    _: KW_ONLY
    role: Literal["admin", "member"] = "member"
    state: Literal["active", "pending"] = "active"


@dataclass
class Member(Entity):
    data: MemberData

    @property
    def user(self) -> User:
        return self.gh.get_user(self.data.login)

    @property
    def org(self) -> Organization:
        return self.gh.get_org(self.data.org)

    def payload(self, /, **ovrr):
        ret = asdict(self.data)
        ret.pop("org")
        return (
            ret
            | {
                "url": f"{self.gh.base_url}/orgs/{self.data.org}/memberships/{self.data.login}",
                "user": self.user.payload(),
            }
            | ovrr
        )


@dataclass
class TeamMemberData(EntityData):
    login: UserName
    org: OrgName
    team: TeamName
    _: KW_ONLY
    role: Literal["maintainer", "member"] = "member"
    state: Literal["active", "pending"] = "active"


@dataclass
class TeamMember(Entity):
    data: TeamMemberData

    @property
    def user(self) -> User:
        return self.gh.get_user(self.data.login)

    @property
    def org(self) -> Organization:
        return self.gh.get_org(self.data.org)

    @property
    def team(self) -> "Team":
        return self.org.get_team(self.data.team)

    def payload(self, /, **ovrr):
        ret = asdict(self.data)
        ret.pop("login")
        ret.pop("org")
        ret.pop("team")
        return (
            ret
            | {
                "url": (
                    f"{self.gh.base_url}/organizations/{self.org.id}"
                    f"/team/{self.team.id}/memberships/{self.data.login}"
                ),
            }
            | ovrr
        )


@dataclass
class RepoData(EntityData):
    name: RepoName
    owner: ActorName
    _: KW_ONLY
    owner_type: Literal["org", "user"] = "org"
    description: str | None = None
    homepage: str | None = None
    private: bool = False
    fork: bool = False
    language: str = "Python"
    default_branch: str = "main"
    has_issues: bool = True
    has_wiki: bool = True
    has_downloads: bool = True

    def __post_init__(self):
        super().__post_init__()
        if self.description is None:
            self.description = f"Test repo {self.name}"

    @property
    def repo_id(self):
        return RepoId(self.owner, self.name)

    @property
    def full_name(self):
        return f"{self.owner}/{self.name}"


@dataclass
class Repo(Entity):
    data: RepoData

    @property
    def owner(self) -> User | Organization:
        if self.data.owner_type == "org":
            return self.gh.get_org(self.data.owner)
        return self.gh.get_user(self.data.owner)

    @property
    def milestones(self) -> "EntityView[str, Milestone]":
        return EntityView(
            {
                data.title: Milestone(self.gh, data)
                for data in self.gh.milestones[self.data.repo_id].values()
            }
        )

    @property
    def rulesets(self) -> "EntityView[str, Ruleset]":
        return EntityView(
            {
                data.name: Ruleset(self.gh, data)
                for data in self.gh.rulesets_repo[self.data.repo_id].values()
            }
        )

    def add_ruleset(self, name: str, **params) -> "Ruleset":
        owner = self.owner
        if not isinstance(owner, Organization):
            raise NotImplementedError
        ruleset = RepoRulesetData(name, self.data.repo_id, **params)
        return self.gh.add(ruleset)

    def get_ruleset(self, rs_id: int | str, *, exc=NotFound) -> "Ruleset":
        rs_id = int(rs_id)
        if rs_id not in self.gh.rulesets_repo[self.data.repo_id]:
            raise exc(f"Repo ruleset with id {rs_id} does not exist for repo {self.data.repo_id}")
        return Ruleset(self.gh, self.gh.rulesets_repo[self.data.repo_id][rs_id])

    def remove_ruleset(self, rs_id: int | str, *, exc=NotFound):
        rs_id = int(rs_id)
        if rs_id not in self.gh.rulesets_repo[self.data.repo_id]:
            raise exc(f"Repo ruleset with id {rs_id} does not exist for repo {self.data.repo_id}")
        del self.gh.rulesets_repo[self.data.repo_id][rs_id]

    def add_milestone(
        self, title: str, creator: User | UserData | UserName, **params
    ) -> "Milestone":
        owner = self.owner
        if not isinstance(owner, Organization):
            raise NotImplementedError
        milestone = MilestoneData(
            title,
            self.data.repo_id,
            creator if isinstance(creator, UserName) else creator.login,
            **params,
        )
        self.gh.add(milestone)
        return Milestone(self.gh, milestone)

    def get_milestone(self, number: int | str, *, exc=NotFound) -> "Milestone":
        number = int(number)
        if number not in self.gh.milestones[self.data.repo_id]:
            raise exc(f"Milestone with number {number} does not exist for repo {self.data.repo_id}")
        return Milestone(self.gh, self.gh.milestones[self.data.repo_id][number])

    @property
    def issues(self) -> "EntityView[str, Issue]":
        return EntityView(
            {
                data.title: Issue(self.gh, data)
                for data in self.gh.issues[self.data.repo_id].values()
            }
        )

    @property
    def pulls(self) -> "EntityView[str, PullRequest]":
        return EntityView(
            {
                data.title: PullRequest(self.gh, data)
                for data in self.gh.pulls[self.data.repo_id].values()
            }
        )

    def add_issue(self, title: str, creator: User | UserData | UserName, **params) -> "Issue":
        issue = IssueData(
            title,
            self.data.repo_id,
            creator if isinstance(creator, UserName) else creator.login,
            **params,
        )
        return self.gh.add(issue)

    def get_issue(self, number: int | str, *, exc=NotFound) -> "Issue":
        number = int(number)
        if number not in self.gh.issues[self.data.repo_id]:
            raise exc(f"Issue with number {number} does not exist for repo {self.data.repo_id}")
        return Issue(self.gh, self.gh.issues[self.data.repo_id][number])

    def add_pull(self, title: str, creator: User | UserData | UserName, **params) -> "PullRequest":
        pull = PullRequestData(
            title,
            self.data.repo_id,
            creator if isinstance(creator, UserName) else creator.login,
            **params,
        )
        return self.gh.add(pull)

    def get_pull(self, number: int | str, *, exc=NotFound) -> "PullRequest":
        number = int(number)
        if number not in self.gh.pulls[self.data.repo_id]:
            raise exc(
                f"Pull request with number {number} does not exist for repo {self.data.repo_id}"
            )
        return PullRequest(self.gh, self.gh.pulls[self.data.repo_id][number])

    def team_payload(self, permission, /, **ovrr):
        rend = self.payload()
        rend["permissions"] = {
            "admin": permission == "admin",
            "push": permission in ("push", "admin"),
            "pull": True,
        }
        return rend | ovrr

    def payload(self, /, **ovrr):
        rend = super().payload() | {
            "full_name": self.data.full_name,
            "owner": {"login": self.data.owner},
            "url": f"{self.gh.base_url}/repos/{self.data.full_name}",
            "html_url": f"https://github.example.com/{self.data.full_name}",
            "size": 100,
            "stargazers_count": 1,
            "watchers_count": 1,
            "watchers": 1,
            "forks": 0,
            "open_issues": 0,
            "open_issues_count": 0,
        }
        rend.pop("owner_type")
        return rend | ovrr


@dataclass
class TeamData(EntityData):
    name: str
    org: OrgName
    _: KW_ONLY
    slug: TeamName = field(init=False)
    description: str | None = None
    privacy: str = "closed"
    permission: Literal["pull", "push", "admin"] = "pull"
    members: dict[UserName, TeamMemberData] = field(default_factory=dict)
    repos: dict[RepoId, Literal["pull", "triage", "push", "maintain", "admin"] | str] = field(
        default_factory=dict
    )

    def __post_init__(self):
        super().__post_init__()
        self.slug = self.name.lower().replace(" ", "-")
        if self.description is None:
            self.description = f"Awesome Team: {self.name}"


@dataclass
class Team(Entity):
    data: TeamData

    @property
    def members(self) -> "EntityView[UserName, TeamMember]":
        return EntityView(
            {login: TeamMember(self.gh, member) for login, member in self.data.members.items()}
        )

    @property
    def repos(self) -> "EntityView[RepoId, str]":
        # Keyed by RepoId, but str/(owner, name) keys are resolved as well.
        def resolve(key) -> RepoId:
            if isinstance(key, str):
                if "/" in key:
                    return RepoId.from_str(key)
                return RepoId(self.data.org, key)
            return RepoId.from_seq(key)

        return EntityView(self.data.repos, resolve=resolve)

    @property
    def org(self) -> "Organization":
        return self.gh.get_org(self.data.org)

    def get_member(self, member: User | UserData | UserName) -> TeamMember | None:
        login = member if isinstance(member, UserName) else member.data.login
        if login not in self.data.members:
            return None
        return TeamMember(self.gh, self.data.members[login])

    def add_member(self, member: User | UserData | UserName, **params) -> TeamMember:
        login = member if isinstance(member, UserName) else member.login
        self.org.add_member(login)  # idempotent
        membership = TeamMemberData(login=login, org=self.data.org, team=self.data.slug, **params)
        self.data.members[login] = membership
        return TeamMember(self.gh, membership)

    def remove_member(self, member: User | UserData | UserName):
        login = member if isinstance(member, UserName) else member.data.login
        self.data.members.pop(login, None)

    def add_repo(
        self,
        repo: Repo | RepoData | RepoName,
        permission: Literal["pull", "triage", "push", "maintain", "admin"] | str = "pull",
        *,
        exc=NotFound,
    ):
        if isinstance(repo, RepoName):
            repo_id = RepoId(self.data.org, repo)
        else:
            assert repo.data.owner == self.data.org
            repo_id = repo.data.repo_id
        if repo_id not in self.gh.repos:
            raise exc(f"Repo {repo_id=} does not exist")
        self.data.repos[repo_id] = permission or "pull"

    def remove_repo(
        self,
        repo: Repo | RepoData | RepoName,
    ):
        if isinstance(repo, RepoName):
            repo_id = RepoId(self.data.org, repo)
        else:
            repo_id = repo.data.repo_id
        self.data.repos.pop(repo_id, None)

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        rend.pop("members")
        rend.pop("repos")
        org = self.org
        return (
            rend
            | {
                # Like the real API, advertise the modern by-ID URL
                "url": f"{self.gh.base_url}/organizations/{org.id}/team/{self.data.id}",
                "html_url": f"https://github.example.com/orgs/{self.data.org}/teams/{self.data.slug}",
                "organization": org.payload(),
            }
            | ovrr
        )


@dataclass
class RulesetData(EntityData):
    name: str
    _: KW_ONLY
    enforcement: Literal["disabled", "active", "evaluate"] = "active"
    target: Literal["branch", "tag", "push"] = "branch"
    created_at: str = CREATED_AT
    updated_at: str = CREATED_AT


@dataclass
class RepoRulesetData(RulesetData):
    source: RepoId


@dataclass
class OrgRulesetData(RulesetData):
    source: OrgName


@dataclass
class Ruleset(Entity):
    data: RepoRulesetData | OrgRulesetData

    def source(self) -> Repo | Organization:
        if isinstance(self.data.source, RepoId):
            return self.gh.get_repo(self.data.source)
        return self.gh.get_org(self.data.source)

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        rend["source"] = str(rend["source"])  # render RepoID
        rend["source_type"] = (
            "Repository" if isinstance(self.data, RepoRulesetData) else "Organization"
        )
        return rend | ovrr


@dataclass
class IssueCommentData(EntityData):
    issue: int
    repo: RepoId
    creator: UserName
    body: str
    _: KW_ONLY
    created_at: str = CREATED_AT
    updated_at: str = CREATED_AT

    def __post_init__(self):
        # Comments carry no login/name/title, derive the ID from their contents.
        self.id = zlib.crc32(f"{type(self).__name__}/{self.repo}#{self.issue}/{self.body}".encode())


@dataclass
class IssueComment(Entity):
    data: IssueCommentData

    @property
    def user(self) -> User:
        return self.gh.get_user(self.data.creator)

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        rend.pop("issue")
        rend.pop("repo")
        rend.pop("creator")
        return (
            rend
            | {
                "url": f"{self.gh.base_url}/repos/{self.data.repo}/issues/comments/{self.data.id}",
                "html_url": (
                    f"https://github.example.com/{self.data.repo}/issues/"
                    f"{self.data.issue}#issuecomment-{self.data.id}"
                ),
                "user": self.user.payload(),
            }
            | ovrr
        )


@dataclass
class IssueData(EntityData):
    title: str
    repo: RepoId
    creator: UserName
    number: int = -1
    _: KW_ONLY
    state: str = "open"
    body: str = ""
    labels: list[str] = field(default_factory=list)
    assignee: UserName | None = None
    milestone: str | None = None  # milestone title
    created_at: str = CREATED_AT
    updated_at: str = CREATED_AT
    comments: dict[int, IssueCommentData] = field(default_factory=dict)


@dataclass
class Issue(Entity):
    data: IssueData

    @property
    def user(self) -> User:
        return self.gh.get_user(self.data.creator)

    @property
    def comment_list(self) -> "EntityView[int, IssueComment]":
        return EntityView(
            {cid: IssueComment(self.gh, data) for cid, data in self.data.comments.items()}
        )

    def add_comment(self, creator: User | UserData | UserName, body: str, **params) -> IssueComment:
        login = creator if isinstance(creator, UserName) else creator.login
        comment = IssueCommentData(self.data.number, self.data.repo, login, body, **params)
        self.data.comments[comment.id] = comment
        return IssueComment(self.gh, comment)

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        rend.pop("comments")
        rend.pop("creator")
        rend.pop("repo")
        rend["labels"] = [{"name": label} for label in self.data.labels]
        rend["assignee"] = {"login": self.data.assignee} if self.data.assignee else None
        rend["milestone"] = {"title": self.data.milestone} if self.data.milestone else None
        return (
            rend
            | {
                "url": f"{self.gh.base_url}/repos/{self.data.repo}/issues/{self.data.number}",
                "html_url": f"https://github.example.com/{self.data.repo}/issues/{self.data.number}",
                "user": self.user.payload(),
            }
            | ovrr
        )


@dataclass
class PullRequestData(EntityData):
    title: str
    repo: RepoId
    creator: UserName
    number: int = -1
    _: KW_ONLY
    state: str = "open"
    body: str = ""
    base: str = "main"
    head: str = "feature"
    created_at: str = CREATED_AT
    updated_at: str = CREATED_AT


@dataclass
class PullRequest(Entity):
    data: PullRequestData

    @property
    def user(self) -> User:
        return self.gh.get_user(self.data.creator)

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        rend.pop("creator")
        rend.pop("repo")
        rend["base"] = {"ref": self.data.base}
        rend["head"] = {"ref": self.data.head}
        return (
            rend
            | {
                "url": f"{self.gh.base_url}/repos/{self.data.repo}/pulls/{self.data.number}",
                "html_url": f"https://github.example.com/{self.data.repo}/pull/{self.data.number}",
                "user": self.user.payload(),
            }
            | ovrr
        )

    def issue_payload(self, /, **ovrr):
        """
        Render the pull request as it appears in the issues list, which
        includes pull requests marked with a ``pull_request`` key.
        """
        rend = self.payload()
        rend.pop("base")
        rend.pop("head")
        return (
            rend
            | {
                "labels": [],
                "assignee": None,
                "milestone": None,
                "pull_request": {
                    "url": f"{self.gh.base_url}/repos/{self.data.repo}/pulls/{self.data.number}",
                },
            }
            | ovrr
        )


@dataclass
class MilestoneData(EntityData):
    title: str
    repo: RepoId
    creator: UserName
    number: int = -1
    _: KW_ONLY
    state: str = "open"
    description: str | None = None
    open_issues: int = 1
    closed_issues: int = 0
    created_at: str = CREATED_AT
    updated_at: str = CREATED_AT
    due_on: str | None = None


@dataclass
class Milestone(Entity):
    data: MilestoneData

    @property
    def creator(self) -> User:
        return self.gh.get_user(self.data.creator)

    @property
    def repo(self) -> Repo:
        return self.gh.get_repo(self.data.repo)

    def payload(self, /, **ovrr):
        rend = asdict(self.data)
        return (
            rend
            | {
                "creator": self.creator.payload(),
                "html_url": f"https://github.example.com/{self.data.repo}/milestone/{self.data.number}",
                "labels_url": f"https://github.example.com/{self.data.repo}/milestone/{self.data.number}/labels",
            }
            | ovrr
        )
