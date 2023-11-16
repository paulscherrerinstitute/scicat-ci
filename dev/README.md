# Local Development

## Overview

Development can be done running local docker containers. First `docker-compose` is used to launch containers for each service. Most containers do not start the service directly, allowing this to be done manually from inside the container (eg using VS Code Dev Containers). Commands for each service are given below.

## Clone the repo and the submodules

```bash
git clone git@github.com:paulscherrerinstitute/scicat-ci.git
git submodule update --init --recursive --remote
```

## Starting containers

### :warning: IMPORTANT
The docker-compose builds the containers from the Dockerfile of each submodule, thus using the submodule checked out to a particular commit.
It is often the case that when setting up the environment one wants the components to be checked out automatically to the latest on main. The command above (`git submodule update --init --recursive --remote`) does that but might break any component where a non-backwards compatible change was applied. 
We reference in the config of each components the latest commit (.git-commit-sha) of the submodule where the docker-compose was run and worked the last time, whenever the submodule commit is different from the one referenced in the scicat-ci repo. 

To build a container based on a different commit one has to checkout first the submodule to the commit (or branch) of interest.

Build the docker containers with the suitable [profiles](https://docs.docker.com/compose/profiles/): 

```bash
export COMPOSE_PROFILES=<MY_PROFILES>
docker-compose -f docker-compose.yaml up -d --force-recreate --build --no-deps
```

All the application containers (excluding the db -mongo- and the db_seeding -mongo_seed-) are meant to be used for development so docker-compose starts, rather than the applications, environments where the development environment of each application is set up. This means that, to run the application, one has to attach to the container and start it. 

### Examples

Here are the two most common use cases, spinning up the backend and fronted; the new backend and the frontend. 

#### BE and FE

1. Export the COMPOSE_PROFILES:
```bash
export COMPOSE_PROFILES=be,fe
```
2. run docker-compose:
```bash
docker-compose -f docker-compose.yaml up --force-recreate --build --no-deps -d
```

This will start four containers: the be container, the fe one, the mongodb database and a short-lived one, called mongodb_seed_be that puts some example data into the be db of mongo.

#### New BE and FE

1. Export the COMPOSE_PROFILES:
```bash
export COMPOSE_PROFILES=be_next,fe
```
2. run docker-compose:
```bash
docker-compose -f docker-compose.yaml up --force-recreate --build --no-deps -d
```

As before, this will start four containers: the be_next container, the fe one, the mongo database and a short-lived one, called mongodb_seed_be_next that puts some example data into the be_next db of mongo.

Since the configuration of the frontend with the new backend has slightly changed, remember to set the `accessTokenPrefix` value to "Bearer " in the [config.json](./config/frontend/config.json#L3) file of the fe, before starting the frontend application.


## Starting services

The `docker-compose.yaml` file is constructed to prepare containers with all dependencies but not to start the services. This is generally done by overriding the command with an infinite loop.

### Backend `be`

```bash
cd /home/node/app
npm run start
```

### Backend-next `be_next`

```bash
cd /home/node/app
npm run start
```

### Frontend `fe`

The frontend uses a custom Dockerfile with the following modifications:

```bash
cd /frontend
npm run start -- --host 0.0.0.0 --disable-host-check
```

A custom Dockerfile is used because the production image builds the static site and then serves it via nginx. The development image serves the site using `ng serve` (webpack-dev-server) so it reflects the latest code and updates when files change.

### Search `search`

```
cd /home/node/app
npm run start
```

### Landing Page `lp`

```bash
cd /home/node/app
npm run start -- --host 0.0.0.0 --disable-host-check
```

### OAI-PMH `oi`

```bash
cd /home/node/app
npm run start
```

### Proposals `pr`

```bash
cd /usr/src/proposals
python src/main.py
```

### Jupyter

Simply browse to localhost:8888

## Reclaiming space

This compose file creates a new docker volume with test data. Removing this requires adding `--volumes` when shutting down the containers:

```bash
docker-compose -f docker-compose.yaml down --volumes
```

If this is omitted it may eventually lead to your docker virtual disk filling up. If this happens, remove old volumes:

```bash
docker volume prune
docker system prune -v
```