#!/bin/bash
cd /app

# Read .env if present
if [ -f .env ]; then
    source .env
fi
export SCICAT_SERVICE_USER_USERNAME SCICAT_SERVICE_USER_PASSWORD

# Allow globus-proxy variable names as alternatives to the globus-cli versions
export GLOBUS_CLI_CLIENT_ID=${GLOBUS_CLI_CLIENT_ID:-$GLOBUS_CLIENT_ID}
export GLOBUS_CLI_CLIENT_SECRET=${GLOBUS_CLI_CLIENT_SECRET:-$GLOBUS_CLIENT_SECRET}

# Start the cleanup script
date -u +"%Y-%m-%dT%H:%M:%SZ  RUN: python scicat_globus_cleaner.py "$@""
exec python scicat_globus_cleaner.py "$@"
