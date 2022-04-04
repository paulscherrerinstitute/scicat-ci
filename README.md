# scicat-ci
CI related information to deploy SciCat

# Deployment behaviour
The CI is responsible of deploying the SciCat components in a k8s clusters (one for `development`, another for `qa` and `production`), based on some rules.
## Development CI
When opening a merge request to the `main` branch, the CI inspects which files were changed. It then triggers the deployment of the modified SciCat component to the `development` environment. 

## QA CI

Once the merge request CI is successful, the user can merge on the `main` branch. If any of the `qa` files were modified, this triggers the deployment on the `qa` environment of the modified component.

## Production CI

The deployment on `production` is managed by using a naming convention on tags names on release. Whenever the user creates a new release, the CI checks the prefix of the tag and deploys the corresponding component on `production`.