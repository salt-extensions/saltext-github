(github-configuration)=
# Configuration

All modules provided by this extension read their configuration from
*profiles*:

(profile-explanation)=
profile
: A profile is a mapping under a top-level key in the minion
  configuration, minion pillar or master configuration
  (grains work also, but should not contain secrets such as the required {ghconf}`token`).
  Functions and states use the profile named `github` by default and accept a
  `profile` argument to select a different one.

(profile)=
## Profile parameters
A profile contains authentication credentials and default configuration
the modules included in this Salt extension reference when running.
The following keys can be specified in the profile:

:::{ghconf} token
:::
`token`
: Required. Access token to authenticate with.

:::{ghconf} owner
:::
`owner`
: Default owner (organization or user) whose resources are managed with this profile.
  Defaults to the token's user, if the token has one.

  This value can be overridden per call via the `owner` argument.

  Needs to be set explicitly when the token does not have an associated
  resolvable user account such as GitHub App installation tokens.

  :::{versionadded} 1.1.0
  Renamed from `org_name`. The new {py:mod}`github_repo <saltext.github.modules.github_repo>`
  modules can manage user repositories in addition to organization ones.
  `org_name` keeps being supported as a legacy alias.
  :::

:::{ghconf} repo_name
:::
`repo_name`
: The default repository the `github_repo` {py:mod}`functions <saltext.github.modules.github_repo>`
  and {py:mod}`states <saltext.github.states.github_repo>` operate
  on when no `repo_name` is passed as an argument.
  Does not affect the `github` {py:mod}`resource module <saltext.github.resources.github>`.

:::{ghconf} allow_repo_privacy_changes
:::
`allow_repo_privacy_changes`
: Allow automated repository privacy modifications. Defaults to false since
  it can be dangerous to change the privacy of a repository in an automated way.

:::{ghconf} api_url
:::
`api_url`
: Base URL of the GitHub API. Set this when targeting a GitHub
  Enterprise Server instance, e.g. `https://github.example.com/api/v3`.
  Defaults to `https://api.github.com`.

## Multiple profiles

Any number of profiles can be defined and selected per call:

```{code-block} yaml
:caption: e.g. `/etc/salt/minion.d/github.yml` or `/srv/pillar/github.sls` with associated mapping in `top.sls`
github:
  token: hunter2
  owner: my_organization

my_user:
  token: hunter3
```

```bash
salt-call github_repo.list profile=my_user
```

## Secret management

Profile values containing [SDB URIs](https://docs.saltproject.io/en/latest/topics/sdb/index.html)
are rendered on access, which also works in pillar-sourced profiles:

```{code-block} yaml
:caption: e.g. `/etc/salt/minion.d/sdb.yml`
osenv:
  driver: env
```

```{code-block} yaml
:caption: e.g. `/etc/salt/minion.d/github.yml` or `/srv/pillar/github.sls` with associated mapping in `top.sls`
# Requires a corresponding SDB profile in the minion configuration, see above
github:
  token: sdb://osenv/GITHUB_TOKEN
  owner: my_organization
```

(github-resource-configuration)=
## Repository resource declaration

:::{versionadded} 1.1.0
:::

The {py:mod}`github repository resource <saltext.github.resources.github>`
(Salt 3008.3+, see the {ref}`repository resources guide <repo-resources>`) is
declared in the managing minion's pillar, under the subtree selected by
the {conf_minion}`resource_pillar_key` minion option (default: `resources`).

:::{hint}
The referenced profiles are resolved from the managing minion's own
data, mirroring {py:func}`config.get <salt.modules.config.get>`'s lookup order – minion configuration,
grains, pillar and master configuration (which reaches the minion via
the master's {conf_master}`pillar_opts` setting) – including SDB rendering.
:::

:::{ghconf} resource:profile
:::
`profile`
: Name of the default {ref}`profile <profile>` for exposed `github` repository resources.
  Defaults to `github`.

:::{ghconf} resource:owners
:::
`owners`
: Owners (organizations or users) whose repositories to manage.
  Defaults to the default profile's {ghconf}`owner` (or the token's
  user when unset). Either a plain list of owner names, or a mapping
  that overrides any of the other declaration keys per owner – e.g. a
  different {ghconf}`profile <resource:profile>` when the repositories
  span credentials (separate tokens per organization, or a mix of
  github.com and a GitHub Enterprise Server instance), or per-owner
  repository selection:

  ```{code-block} yaml
  :caption: Plain list
  owners:
    - my-github-handle
    - my-org
  ```

  ```{code-block} yaml
  :caption: Mapping with overrides for other declaration-level configs
  owners:
    my-github-handle:
      exclude:
        - not-this
    other-org:
      profile: other_github_org
  ```

  Keys an owner does not override are inherited from the declaration
  level.

:::{ghconf} resource:repos
:::
`repos`
: List of fnmatch patterns selecting the repositories to manage.
  Patterns containing a slash match the full name (`owner/repo`),
  others the bare repository name. Defaults to all repositories.
  Can be overridden per owner in the {ghconf}`owners <resource:owners>`
  mapping.

:::{ghconf} resource:exclude
:::
`exclude`
: List of fnmatch patterns excluding repositories, following the same
  matching rules as {ghconf}`repos <resource:repos>` and applied after
  it. Defaults to none.
  Can be overridden per owner in the {ghconf}`owners <resource:owners>`
  mapping.

:::{ghconf} resource:include_archived
:::
`include_archived`
: Include archived repositories. Defaults to false.
  Can be overridden per owner in the {ghconf}`owners <resource:owners>`
  mapping.

### Minimal example config
This example showcases the minimally required config to use the modules
and expose repositories as Salt resources.

```{code-block} yaml
:caption: e.g. `/etc/salt/minion.d/github.yml` or `/srv/pillar/github.sls` with associated mapping in `top.sls`
# Specify the default token.
# If this is a PAT, it targets repositories owned by you, unless `owner` is specified explicitly.
github:
  token: foobar

# Expose all your repositories as `github:your-handle/your-repo` resources.
resources:
  github: {}
```

### Full example config
This example showcases an intricate config for different actors/orgs
and repo resource selection while avoiding to include plain text tokens in the config.

```{code-block} yaml
:caption: e.g. `/etc/salt/minion.d/sdb.yml`
# SDB profile for the `env` SDB module.
# Exposes environment variables as `sdb://osenv/<ENV_VAR_NAME>` URIs.
osenv:
  driver: env

# SDB profile for the `vault` SDB module.
# Exposes Vault secrets as `sdb://sdbvault/<mount>/<secret_path>?<secret_key>` URIs.
sdbvault:
  driver: vault
```

```{code-block} yaml
:caption: e.g. `/etc/salt/minion.d/github.yml` or `/srv/pillar/github.sls` with associated mapping in `top.sls`
# The default profile when not overridden in the function call
github:
  token: sdb://sdbvault/secrets/my_github?token
  allow_repo_privacy_changes: true
  # This is resolved automatically if the token is associated with your user account:
  # owner: my-github-handle

# Same token, but this profile defaults to organization scope when no `owner` is passed
my_github_org:
  token: sdb://sdbvault/secrets/my_github?token
  owner: my-org

# Different token and API endpoint for another organization.
other_enterprise_org:
  api_url: https://github.example.com/api/v3
  token: sdb://osenv/GITHUB_TOKEN
  owner: other-org

# Expose specific repositories as resources
resources:
  github:
    owners:
      my-github-handle: {}
      my-org:
        exclude:
          - foo-not-this-repo
      other-org:
        profile: other_enterprise_org
        repos:
          - bar-*
        include_archived: false
    repos:
      - foo-*
    include_archived: true
```
