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

:::{ghconf} resource:grains_files
:::
`grains_files`
: Custom resource grains sourced from YAML/JSON files inside each
  repository. A mapping of grain namespace to file specification –
  each namespace becomes a grain key next to the builtin ones
  (`id`, `owner`, `repo`, ..., which namespaces must not shadow).
  The special `_` namespace instead merges its keys into the root
  grains level; keys that already exist – the builtin identity grains
  or earlier namespaces – are never overwritten.

  `path`
  : File path(s) inside the repository, a string or a list. All listed
    files are fetched; missing ones are skipped and the parsed mappings
    are shallow-merged in list order, earlier files winning.

  `include`
  : Optional list of strings or single-key dicts selecting the exposed keys.

    String entries are fnmatch patterns matched case-sensitively against
    colon-delimited key paths; a match includes the whole subtree, preserving nesting.
    `*` crosses `:` boundaries.

    Single-entry mappings rename:
    the value at the exact source path (scalar or subtree, no patterns)
    is exposed under the new name as a flat or nested namespace key.

    A plain mapping of new name to source path is shorthand for a
    list of mostly renames. Unset means everything is included.

    See the [Full example config][full-example-config] for detailed syntax examples.

  `exclude`
  : Optional list of fnmatch patterns pruning matching key paths at
    any depth, applied after `include`. Does not apply to renamed
    keys. Note that `*` also crosses `:` boundaries.

  Can be overridden per owner in the {ghconf}`owners <resource:owners>`
  mapping. Unlike the other keys, the override replaces the
  declaration-level value entirely (no merging) – an empty mapping
  thus disables custom grains for that owner.

  :::{important}
  These grains are controlled by anyone who can commit to the
  respective repository. Restrict the exposed keys via `include`
  allowlists and keep that trust model in mind when building targeting
  expressions. The builtin identity grains cannot be shadowed.
  :::

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

# Expose select repositories as resources
resources:
  github:

    # By default, for any owner, only expose repositories that start with `foo-`,
    # including archived ones.
    include_archived: true
    repos:
      - foo-*

    # Also try to load a file named `.github/data.json` from each repository and
    # include all keys but those starting with an underscore in grains["data"]
    grains_files:
      data:
        path: .github/data.json
        exclude:
          - "_*"

    # Expose repositories specifically from these accounts.
    owners:

      # Use the defaults above. Exposed are: my-github-handle/foo-*
      my-github-handle: {}

      # Exclude archived ones and a specific one. Exposed are my-org/foo-*,
      # but not the one repository named my-org/foo-not-this-repo.
      my-org:
        exclude:
          - foo-not-this-repo
        include_archived: false

      # Expose repositories matching other-org/bar-* while using a different profile.
      # Don't render any custom grains from files in these repositories.
      other-org:
        profile: other_enterprise_org
        grains_files: {}
        repos:
          - bar-*

      # Reset `repos` config to expose all repos.
      # Showcase custom grains (in detail).
      tiny-org:
        # Reset repo selection to include all repos in tiny-org/*.
        repos: {}
        # Override the default custom file grains config completely
        grains_files:

          # When a repo has a `.github/grains.json` file, load it and merge
          # select keys (by "glob" match) into the repository's grains (no namespace).
          # You can rename keys by passing a single-key dict
          # (no globs allowed in source or target).
          # Explicit renames always win a slot.
          # Note: inbuilt grains can never be overridden.
          _:
            path: .github/grains.json
            include:
              - team
              - status
              - nested:key
              - 'include-all-*'
              - '*-also-these'
              - 'and-*-these'
              - 'and:*-these'  # a glob spans nesting levels
              - some_key: renamed:from:a:deeply:nested:key
              - some:nested:target: renamed:from:another:deeply:nested:key

          # Try loading several paths and merge their data into the `data` namespace in grains.
          # If more than one file specifies the same key, the *first* one wins.
          # This one still excludes any keys that start with an underscore, but shows
          # exclude/include can be specified as a simple string.
          data:
            path:
              - .github/foo.json
              - .github/bar.yml
            exclude: _*

          # Namespaces can be nested.
          # `include` can be a mapping as a shorthand if most of your
          # includes are renames. Regular patterns are still supported
          # by specifying a falsy value.
          nested:target:copier:
            path: .copier-answers.yml
            include:
              template_version: _commit
              nested:target: my_question
              nested_source: my:question
              just_keep_this_explicit_key:
              keep_glob_*:stuff: ''
```
