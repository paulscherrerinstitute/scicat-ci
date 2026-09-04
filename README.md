# scicat-ci

CI and deployment configuration to run SciCat at PSI.

For a simpler setup to run and develop the SciCat core components locally, see the
[SciCat Live](https://github.com/SciCatProject/scicatlive) project.

## Repo structure

```
.
├── helm/                    deployment config for every component, see helm/README.md
│   ├── helmfile-common.yaml   shared defaults and the build hook
│   └── configs/<component>/   one folder per component, name = helm release name
├── proposals/               source of the proposals component, built from here
├── scicat-to-pss/           source of the scicat-to-pss component, built from here
├── curation/                notebooks and scripts used to curate data
└── .github/
    ├── workflows/             deploy.yml, lint.yml and their reusable building blocks
    └── actions/                deploy-helmfile, deploy-helm, open-ssh-tunnel
```

Most components (backend, frontend, search-api, ...) live in their own repository
under the [SciCatProject organisation](https://github.com/SciCatProject) and are
built from a published image or from a commit sha, as configured in
`helm/configs/<component>`. A few components (`proposals`, `scicat-to-pss`) live
directly in this repository; their source folder at the root is the build context
referenced by their helm config via `sourceDir`.

## Environments

Every component can be deployed to three environments, each mapped to a k8s cluster
and namespace:

| Environment | K8s cluster | Namespace          |
| ----------- | ----------- | ------------------ |
| development | development | scicat-development |
| qa          | qaprod      | scicat-qa          |
| production  | qaprod      | scicat-production  |

## CI workflows

| Workflow                                                   | Trigger                                         | What it does                                                                                           |
| ---------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| [deploy.yml](.github/workflows/deploy.yml)                 | PR to `main`, push to `main`, release published | Deploys every changed component to the environment matching the trigger                                |
| [lint.yml](.github/workflows/lint.yml)                     | PR to `main`                                    | Renders every changed helmfile state for all three environments, to catch template errors before merge |
| [actionlint.yml](.github/workflows/actionlint.yml)         | PR touching `.github/**`                        | Lints the GitHub Actions workflow files themselves                                                     |
| [proposals-test.yml](.github/workflows/proposals-test.yml) | PR touching `proposals/**`                      | Builds and smoke-tests the proposals component                                                         |

### How deploy.yml picks environment and components

The trigger determines the environment:

- **pull_request → main**: deploys to `development`
- **push → main** (i.e. a merged PR): deploys to `qa`
- **release published**: deploys to `production`, for the single component named by
  the release tag (`<component>-vX.Y.Z`)

For `pull_request` and `push`, the workflow diffs the changed files and deploys only
the components whose `helm/configs/<component>` folder changed (or all of them if
`helm/helmfile-common.yaml` or `deploy.yml` itself changed). A release always
deploys exactly the one component the tag names, regardless of what changed.

### Typical workflow: changing a component's configuration or image

1. Open a branch in this repo.
2. Edit `helm/configs/<component>/values.yaml` (all environments) or
   `helm/configs/<component>/<env>/values.yaml` (one environment) — e.g. to bump an
   image tag or change a chart value.
3. Commit, push, open a PR to `main`. This triggers a deploy to `development`.
4. Merge the PR. This triggers a deploy to `qa`.
5. Create a GitHub release tagged `<component>-vX.Y.Z`. This triggers a deploy to
   `production`.

See [helm/README.md](helm/README.md) for the full set of recipes (deploying a
commit that isn't published yet, adding a component, secrets, etc.).

## Helm / helmfile deployment

Each component under `helm/configs/<component>` is a self-contained helmfile state:
which chart to pull, which values files to apply per environment, which secrets its
chart receives, and — for components without a published image — a build hook that
builds and pushes the image from source before helm runs.

`deploy.yml` renders and applies exactly this state per environment; nothing else in
CI decides what gets deployed or how.

### values.yaml vs helmfile.yaml.gotmpl

Each component folder has both kinds of file, and they are read by two different
tools — a change in the wrong one is silently ignored:

- **`values.yaml` and `<env>/values.yaml`** are read by **helm**, and rendered by
  the chart. Put here anything the chart's templates consume: image
  repository/tag, replica count, ingress host, resource limits, env vars, which
  secret keys the chart expects. This is what you edit for a normal deploy — bump
  an image tag, change a chart setting for one or all environments.
- **`helmfile.yaml.gotmpl`** is read by **helmfile** only, never by the chart. Put
  here anything that decides how helmfile itself behaves: the release name and
  namespace, which chart and version to pull, which values files to layer in for
  an environment, `installed:` (whether the release exists in that environment at
  all), `sourceRepo`/`sourceDir` (build an unpublished commit from source), and
  which secret keys the release is allowed to read out of the environment's
  secrets. References to config files that need to reach the chart as a file
  (the `set: [{name, file}]` block, which becomes `--set-file`) also go here, not
  in `values.yaml` — the path is resolved next to the config, and a `values.yaml`
  cannot express a file reference at all.

Rule of thumb: if it configures a Kubernetes resource the chart creates, it's a
`values.yaml` change. If it configures what helmfile does before/instead of
calling helm, it's a `helmfile.yaml.gotmpl` change.

A commit sha in `image.tag` and a `sourceDir` in `helmfile.yaml.gotmpl` are both
opaque on their own — neither says what branch they came from. When you set
either, add a comment next to it naming the branch, so the next person doesn't
have to dig through the source repo's history to find out.

Full details — how to point a deploy at an unpublished commit, how secrets and
environments are wired, and worked examples of the values.yaml/helmfile split —
are in [helm/README.md](helm/README.md).
