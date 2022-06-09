# scicat-ci
CI related information to deploy SciCat

# Deployment behaviour
The CI is responsible for deploying the SciCat components in the k8s clusters (one for `development`, another for `qa` and `production`), based on some rules.

The whole pipeline relies on the existence of three deployment environments: `development` (where changes are developed), `qa` (beta testing environment) and `production` (stable environment). The components are deployed on one of two clusters depending on the environment. The `development` environment is deployed on the `development` cluster, while the `qa` and `production` environment are deployed on the `qaprod` cluster and are installed under the `scicat-{env}` namespace on the corresponding cluster. For the three GitHub CI triggers, `pull_request` to `main`, `push` to `main` and `release`, the CI extracts the environment based on the trigger (follows), builds, tags and pushes the docker image and deploys the helm chart to the corresponding k8s cluster, having applied the configuration specific to the environment. 
The configuration files are in the [helm_configs](helm_configs) folder and are organised in folders with the same name of the component (convention to be maintained). For each component, the files in `helm_configs/{component}` are shared by all the environments, while the ones specific to one environment are in `helm_configs/{component}/{environment}`. For example, the `backend` configuration files are in the [helm_configs/backend](helm_configs/backend) folder, and the development specific files are in [helm_configs/backend/development](helm_configs/backend/development)

There is no need to explicitly specify the environment, nor the location of the files at CI time, as its value is extracted depending on the GitHub CI trigger.

Some conventions are to be maintained: 

 - the name of the component in the GitHub submodule has to match the name of the config folder in the helm_configs directory. Also, this is the name that will be assigned to the helm release on the cluster.
 - folders inside `helm_configs/{component}`, can only be named `development`, `qa` or `production` as they need to have the same names as the environments since the helm deployment uses the environment name to look for environment-specific folders.

 ## Changes that trigger the pipeline

The whole repo structure relies on the concept of git submodules. Every component is a pointer to the repository in the [SciCatProject organisation](https://github.com/SciCatProject) and as part of the CI the GitHub actions inspect for changes in submodules. The other change that triggers the pipeline is a change in the configuration files and changing the configuration of one of the components triggers the deployment of that component only. All other changes do not trigger a new deployment.

The two common scenarios for which we want a new deployment of a component are: 
 - a change in the configuration of the component
 - a change in the code base of the component (i.e. working on the submodule)

### Workflow when changing the configuration of a component

 1. open a new branch in the scicat-ci repo
 2. make the change in the file of need, which is in `helm_configs/{component}/{environment}`
 3. commit and push the change to the remote
 4. open a PR to `main`. At this point, the pipeline deploying on [development](#development-pipeline) starts.
 5. when ready, merge the PR into `main`. At this point, the pipeline deploying on [qa](#qa-pipeline) starts.
 6. when ready, create a new release. At this point, the pipeline deploying on [production](#production-pipeline) starts.

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
When opening a merge request to the `main` branch, the CI inspects which files were changed. If the configuration changed was a `development` one, namely if the file changed is in `helm_configs/{component}/development` or there is a change in the component submodule, then the component is deployed on the `development` cluster, otherwise, no deployment on `development` takes place.

## QA pipeline

Once the merge request CI is successful, the user can merge on the `main` branch. If the configuration changed was a `qa` one, namely if the file changed is in `helm_configs/{component}/qa` or there is a change in the component submodule, then the component is deployed on the `qaprod` cluster, using the `scicat-qa` namespace, otherwise, no deployment on `qa` takes place.

## Production pipeline

The deployment on `production` is managed by using a naming convention on tags names on release. Whenever the user creates a new release, the CI checks the prefix of the tag and, independently of the changes, deploys the corresponding component on `production`, i.e. on the `qaprod` cluster, using the `scicat-production` namespace. 

Below are the existing components with their prefix, in the format `component: prefix`:

 - frontend: `fe`
 - backend: `be`
 - search-api: `sa`
 - pan-ontologies-api: `po`
 - oaipmh: `oa`
