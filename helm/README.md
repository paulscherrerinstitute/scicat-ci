# helm

Deployment configuration for every SciCat component at PSI.

## What is here

```
helm/
  helmfile-common.yaml        shared defaults and the build hook
  configs/<component>/
    helmfile.yaml.gotmpl      the helmfile state, add it to use deploy.yml
    values.yaml               chart values, all environments
    <env>/values.yaml         chart values, one environment
```

## Two deploy paths

A component with a `helmfile.yaml.gotmpl` deploys through `.github/workflows/deploy.yml`.
A component without one still deploys through its own `.github/workflows/scicat-*.yml`.

```sh
ls helm/configs/*/helmfile.yaml.gotmpl    # the components that use deploy.yml
```

The migration runs one component at a time. Add the config and delete the
component's own workflow in the same commit. Otherwise both run `helm upgrade` on
the same release.

## Recipes

### Change the configuration of a component

Edit `values.yaml` for every environment, or `<env>/values.yaml` for one. Open a PR.
The pipeline deploys to development on the PR, to qa on merge, and to production on
a release.

### Deploy a different published image

Change the tag in `values.yaml`, or in `<env>/values.yaml` to move one environment
alone.

### Deploy a commit that nobody published

Set the source repository, and point `image` in `values.yaml` at the commit to
build. The hook reads `image` out of the same values files the release lists, so the
state names the source repository alone. Set only the environments that build,
because the others keep the pinned image.

```gotmpl
environments:
  development:
    values:
      - sourceRepo: https://github.com/SciCatProject/backend
---
releases:
  - name: backend-next
    ...
    {{ if .Values.sourceRepo }}
    inherit:
      - template: build
    {{ end }}
    values:
      - values.yaml
      - {{ .Environment.Name }}/values.yaml
```

Four rules that nothing enforces. Read them before you set `sourceRepo`.

- **`image.tag` must be a commit sha.** With a branch name, ghcr always has the
  image, so the hook never rebuilds. The deploy then keeps an old image and still
  reports success.
- **`image.repository` must start with `ghcr.io/paulscherrerinstitute/scicat-ci/`.**
  The deploy token writes only packages that this repository owns.
- **The source repository needs a Dockerfile at its root.** buildx uses the
  repository root as the build context.
- A helm rollback does not delete a pushed image.

### Move a component onto deploy.yml

1. Write `helm/configs/<component>/helmfile.yaml.gotmpl`.
2. Copy the image the old workflow deployed into `values.yaml`.
3. Move each `helm_set_files` entry to a `set:` block.
4. Delete `.github/workflows/scicat-<component>.yml` and the submodule.
5. Render all three environments, then open the PR.

## What a config can set

| Field                          | Behaviour                                               |
| ------------------------------ | ------------------------------------------------------- |
| `name`                         | the helm release name, must match the folder name       |
| `namespace`                    | always `scicat-{{ .Environment.Name }}`                 |
| `chart` and `version`          | the OCI chart to pull                                   |
| `values:`                      | chart values files and inline maps, the last entry wins |
| `set: [{name, file}]`          | becomes `--set-file`, paths resolve next to the config  |
| `inherit: [{template: build}]` | adds the build hook                                     |
| `sourceRepo`                   | starts the build, see the recipe above                  |
| `installed`                    | whether the release belongs in this environment         |

### Environments

`deploy.yml` runs a component on all three environments. Name the ones it belongs in.

```gotmpl
    installed: {{ eq .Environment.Name "development" }}
```

**This uninstalls, it does not skip.** A release marked `installed: false` that exists
on the cluster is removed on the next sync. Use it for a retired component, not to
pause a deploy.

Guard the environment values file and the `set:` block the same way when the other
environments have no config to read. A guarded environment renders empty, so
`lint.yml` stops checking its configs.

### Secrets

`deploy.yml` passes every secret of the environment to the state. A release names
the ones its chart receives, one key per line.

```gotmpl
      - secretsJson:
          COMPONENT_CONFIG: {{ .Values.secrets.COMPONENT_CONFIG | quote }}
          DATASOURCES: {{ .Values.secrets.DATASOURCES | quote }}
```

A secret that only one environment defines needs a guard, or the other environments
stop on the missing key. Guard the line when the other keys stay.

```gotmpl
      - secretsJson:
          BENEXT_ENV: {{ .Values.secrets.BENEXT_ENV | quote }}
          {{- if eq .Environment.Name "development" }}
          OPENEM_WHITELISTED_IPS: {{ .Values.secrets.OPENEM_WHITELISTED_IPS | quote }}
          {{- end }}
```

Guard the whole entry when every key it holds is for one environment.

```gotmpl
      {{ if eq .Environment.Name "development" }}
      - secretsJson:
          EXPORTER_WHITELIST_CIDRS: {{ .Values.secrets.EXPORTER_WHITELIST_CIDRS | quote }}
      {{ end }}
```

Keep every form below the `---`. Helmfile renders the whole `environments:` block
before it selects an environment, so a `.Values.secrets` read up there runs for every
deploy and stops qa on a key only development defines.

A missing key always stops the render. That is the wanted behaviour, an empty
whitelist annotation opens the ingress.

The encoding depends on where the value lands. A value in the chart's `secrets:`
block must be base64, and the chart stops the render if it is not. A value used
anywhere else, such as an ingress annotation, is plain text.

## Two kinds of values

Helmfile and helm read different files, and only a command line crosses between
them. Put a value in the wrong one and it is silently ignored.

| File                                  | Read by  | Holds                  |
| ------------------------------------- | -------- | ---------------------- |
| the `environments:` block             | helmfile | what to run            |
| `values.yaml` and `<env>/values.yaml` | helm     | what the manifest says |

A file under a release `values:` never reaches helmfile. A key under `environments:`
never reaches helm. A file that both need is listed twice, which is what the recipe
above does with `values.yaml`.

Chart values files are rendered by the chart, so `{{ .Values.host }}` works in them.
Helmfile never templates them.

## The build hook

`helmfile-common.yaml` holds it. It runs on `presync`, before helm.

1. It asks ghcr for `<image.repository>:<image.tag>`.
2. If ghcr has the image, it prints a message and stops. Nothing is built.
3. If ghcr does not have it, the hook builds `<sourceRepo>.git#<image.tag>` and
   pushes it.

The hook runs on every sync so it would stops a rebuild each time. A non-zero
exit stops the release before helm starts, so a failed build leaves the running
release unchanged. The hook runs on `sync` and `apply` only, so a render builds
nothing and needs no network.

## Render before you push

CI renders every changed config on a PR. Use this for a faster local check.

A config reads `.Values.secretsJson.<KEY>` without a test, so a render needs every
key present. Build a placeholder file once.

```sh
grep -rhoE 'secretsJson\.[A-Za-z0-9_]+' helm/configs | cut -d. -f2 | sort -u \
  | jq -R . | jq -s '{secrets: (map({key: ., value: "ZHVtbXk="}) | from_entries)}' \
  > /tmp/secrets.json
```

Then render one component.

```sh
for env in development qa production; do
  helmfile --file helm/configs/scicat-exporter/helmfile.yaml.gotmpl \
    --environment "$env" --state-values-file /tmp/secrets.json template
done
```

Diff that against the same command on `main` before you push. A change meant to
keep the same behaviour must give an identical render.

`.github/actions/deploy-helmfile/action.yml` pins the helmfile version that CI runs.
