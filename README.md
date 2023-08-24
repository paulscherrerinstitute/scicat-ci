# scicat-ci
CI related information to deploy SciCat

# Local environment

To spin up the container(s) of interest, follow the documentation in the [README](./dev/README.md) in the dev folder.

# Deployment behaviour
The CI is responsible for deploying the SciCat components in the k8s clusters (one for `development`, another for `qa` and `production`), based on some rules.

The whole pipeline relies on the existence of three deployment environments: `development` (where changes are developed), `qa` (beta testing environment) and `production` (stable environment). The components are deployed on one of two clusters depending on the environment. The `development` environment is deployed on the `development` cluster, while the `qa` and `production` environment are deployed on the `qaprod` cluster and are installed under the `scicat-{env}` namespace on the corresponding cluster. For the three GitHub CI triggers, `pull_request` to `main`, `push` to `main` and `release`, the CI extracts the environment based on the trigger (follows), builds, tags and pushes the docker image and deploys the helm chart to the corresponding k8s cluster, having applied the configuration specific to the environment. 
The configuration files are in the [helm/configs](helm/configs) folder and are organised in folders with the same name of the component (convention to be maintained). For each component, the files in `helm/configs/{component}` are shared by all the environments, while the ones specific to one environment are in `helm/configs/{component}/{environment}`. For example, the `backend` configuration files are in the [helm/configs/backend](helm/configs/backend) folder, and the development specific files are in [helm/configs/backend/development](helm/configs/backend/development)

There is no need to explicitly specify the environment, nor the location of the files at CI time, as its value is extracted depending on the GitHub CI trigger.

Some conventions are to be maintained: 

 - the name of the component in the GitHub submodule has to match the name of the config folder in the helm/configs directory. Also, this is the name that will be assigned to the helm release on the cluster.
 - folders inside `helm/configs/{component}`, can only be named `development`, `qa` or `production` as they need to have the same names as the environments since the helm deployment uses the environment name to look for environment-specific folders.

 ## Changes that trigger the pipeline

The whole repo structure relies on the concept of git submodules. Every component is a pointer to the repository in the [SciCatProject organisation](https://github.com/SciCatProject) and as part of the CI the GitHub actions inspect for changes in submodules. The other change that triggers the pipeline is a change in the configuration files and changing the configuration of one of the components triggers the deployment of that component only. All other changes do not trigger a new deployment.

The two common scenarios for which we want a new deployment of a component are: 
 - a change in the configuration of the component
 - a change in the code base of the component (i.e. working on the submodule)

### Workflow when changing the configuration of a component

 1. open a new branch in the scicat-ci repo
 2. make the change in the file of need, which is in `helm/configs/{component}/{environment}`
 3. commit and push the change to the remote
 4. open a PR to `main`. At this point, the pipeline deploying on [development](#development-pipeline) starts.
 5. when ready, merge the PR into `main`. At this point, the pipeline deploying on [qa](#qa-pipeline) starts.
 6. when ready, create a new release. At this point, the pipeline deploying on [production](#production-pipeline) starts.
 
#### Example session for test on development
```
git clone git@github.com:paulscherrerinstitute/scicat-ci.git
git checkout -b configs/testMetadataColumns
cd scicat-ci/helm/configs/frontend/development/
# do your changes and commits
git add helm/configs/frontend/development/environment.ts
git commit -m "New frontend configuration for development to test metadata columns"
git push origin configs/testMetadataColumns 
# follow the PR link given and push the PR on the github webpage
```

### Workflow when working on a submodule

 1. open a new branch in the scicat-ci repo
 2. `cd` into the component submodule (e.g. `cd backend`)
 3. open a new branch in the submodule repo
 4. make the changes in the submodule
 5. commit and push the changes to the submodule remote (e.g. `git push https://github.com/SciCatProject/backend.git`)
 6. `cd ..` back to the scicat-ci repo
 7. commit the change in the submodule reference (e.g. `git commit backend`) and push to the scicat-ci remote (`git push git@github.com:paulscherrerinstitute/scicat-ci.git`)
 8. open a PR to `main`. At this point, the pipeline deploying on [development](#development-pipeline) starts.
 9. when ready, merge the PR into `main`. At this point, the pipeline deploying on [qa](#qa-pipeline) starts.
 10. when ready, create a new release. At this point, the pipeline deploying on [production](#production-pipeline) starts.

## Development pipeline
When opening a merge request to the `main` branch, the CI inspects which files were changed. If the configuration changed was a `development` one, namely if the file changed is in `helm/configs/{component}/development` or there is a change in the component submodule, then the component is deployed on the `development` cluster, otherwise, no deployment on `development` takes place.

## QA pipeline

Once the merge request CI is successful, the user can merge on the `main` branch. If the configuration changed was a `qa` one, namely if the file changed is in `helm/configs/{component}/qa` or there is a change in the component submodule, then the component is deployed on the `qaprod` cluster, using the `scicat-qa` namespace, otherwise, no deployment on `qa` takes place.

## Production pipeline

The deployment on `production` is managed by using a naming convention on tags names on release. Whenever the user creates a new release, the CI checks the prefix of the tag and, independently of the changes, deploys the corresponding component on `production`, i.e. on the `qaprod` cluster, using the `scicat-production` namespace. 

Below are the existing components with their prefix, in the format `component: prefix`:

 - frontend: `fe`
 - backend: `be`
 - search-api: `sa`
 - pan-ontologies-api: `po`
 - oaipmh: `oa`
 - landing-page-server: `lp`


## Deploy.sh

The [deploy.sh](deploy.sh) script should ease the deployment in the development and qa environment, by making use of CI triggers.

The deployment to development is triggered when a pull request to main is opened or when there is a workflow dispatch event. The script makes use of the github APIs to trigger a workflow dispatch event and start a deployment on development. On qa the trigger is a push to main and, so, the script does a push on main when needing to deploy on qa.

### How to use

1. clone the repo and its submodules: 
```
git clone git@github.com:paulscherrerinstitute/scicat-ci.git
git submodule update --recursive --init
```

2. Print out the script options: 
```
./deploy.sh -h
>Input options:
>   -e           deployment environment name. Default to development
>   -w           CI workflow file name. To be specified when environment=development
>   -s           submodule name. Default to scicat
>   -c           CI repo local path. Default to .
>   -b           CI Branch name. Default to the current branch name of the submodule
>   -o           CI origin alias. Default to origin
>   -m           CI Main branch name. Default to main
>   -t           Github token
```

#### Deploy on dev

To deploy on development the workflow to run and the github token must be set, respectively with the -w and -t flags or exporting the env variables. The other options are optional.

```
./deploy.sh -t <YOUR_GITHUB_TOKEN> -w scicat-be.yml
```

This will trigger the deployment of the scicat be using the commit from your submodule (NOTE that this commit must be in the [scicat be](https://github.com/SciCatProject/backend)).

To obtain a suitable token, please follow the [github wiki](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).

#### Deploy on qa

To deploy on qa the environment option must be set, with the -e flag, or exporting the env variable.

```
./deploy.sh -e qa
```

As before, the version which is deployed on qa is the one of the commit from your submodule (NOTE that this commit must be in the [scicat be](https://github.com/SciCatProject/backend)).

### :warning: IMPORTANT

The deploy.sh script belongs to the scicat-ci repo, so it needs to be run from this folder. This means that, when developing on scicat, one still needs to run the following steps: 

1. from scicat-ci `cd` e.g. into backend:
```
cd backend
```
2. commit and push the change to the scicat be repo
3. cd back to scicat-ci:
```
cd ..
```
4. run deploy.sh
```
./deploy.sh
```

This can be eased by creating an alias that sets the -c flag, e.g.: 

```
alias deploy_scicat_be=". <YOUR_PATH_TO_SCICATCI>/deploy.sh -c <YOUR_PATH_TO_SCICATCI>"
```

or exporting the cipath env variable and expanding the PATH:

```
export cipath=<YOUR_PATH_TO_SCICATCI>
PATH=$PATH:<YOUR_PATH_TO_SCICATCI>
```

In this way, it is possible to run the deploy.sh script directly from the e.g. scicat be folder, thus not needing (3).
