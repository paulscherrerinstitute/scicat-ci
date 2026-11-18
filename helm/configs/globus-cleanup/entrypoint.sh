#!/bin/sh
cd /app

pip install --no-cache-dir -r requirements.txt

# Transform the globus-proxy .env file to globus-cli environment variables
source .env
export SCICAT_SERVICE_USER_USERNAME SCICAT_SERVICE_USER_PASSWORD
export GLOBUS_CLI_CLIENT_ID=$GLOBUS_CLIENT_ID
export GLOBUS_CLI_CLIENT_SECRET=$GLOBUS_CLIENT_SECRET

date -u +"%Y-%m-%dT%H:%M:%SZ"
exec python scicat_globus_cleaner.py "$@"
