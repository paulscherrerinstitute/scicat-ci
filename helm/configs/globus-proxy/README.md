# SciCat Globus Proxy

This service proxies globus transfers after checking SciCat credentials.

## Environments

| Env         | URL                             |
| ----------- | ------------------------------- |
| development | globus-proxy.development.psi.ch |
| qa          | scicat-globus-proxy-qa.psi.ch   |
| production  | scicat-globus-proxy.psi.ch      |

OpenEM facilities use the same endpoints for all three. However, the PSI destination
collections are different for each environment.

## Check collections

If a collection is invalid (eg if a facility is down or changes their collection ID) it
causes some problems. It's a good idea to run
[check_collections.sh](https://github.com/SwissOpenEM/scicat-globus-proxy/blob/main/scripts/check_collections.sh)
from the scicat-globus-proxy repo to validate that all collections are readable by the
service user.

```zsh
# set globus service user variables (credentials shared by all envs)
eval $(
  pass show development/scicat/globus_proxy/env \
  | sed -rn 's/^GLOBUS/;export GLOBUS_CLI/p'
)

~/git/scicat-globus-proxy/scripts/check_collections.sh ~/git/scicat-ci/helm/configs/globus-proxy/*/config.yaml
```

This should return 0 and show success:
```
✅ DCIL            success  b3807ed3-db5e-4e6f-9831-fd8d72dfff8a
✅ DEMO            success  394fb902-2fcf-4ffd-ba61-98d72e29dd0e
✅ EMPA            success  ed650f52-0235-4c40-a573-5f8de55841a6
✅ EPFL-LBEM       success  ed650f52-0235-4c40-a573-5f8de55841a6
✅ PSI             success  7a50c4b9-651d-4fba-a8f9-0557f1b4b7ed
✅ PSI_DEV         success  deda66cc-9e42-49fc-a997-18a02abb7903
✅ PSI_QA          success  394fb902-2fcf-4ffd-ba61-98d72e29dd0e
✅ UNIBAS          success  ab30321a-6f8f-488b-bf0a-f5afdd56398d
✅ UNIBE           success  44e61e98-8dba-43ec-a862-c1fe82ac23d6
✅ UNIGE           success  d22fab58-5f80-47f1-a9a0-da36478ca41e
```
