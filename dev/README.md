# How to get started:

## Clone the repo and the submodules

```bash
git clone git@github.com:paulscherrerinstitute/scicat-ci.git
git submodule update --recursive --init
```

## Run docker-compose

### :warning: IMPORTANT 
The docker-compose builds the containers from the Dockerfile of each submodule, thus using the submodule checked out to a particular commit. To build a container basing it on a different commit, e.g. the latest on main, one has to checkout first the submodule to the commit (or branch) of interest.

Build the docker containers with the suitable [profiles](https://docs.docker.com/compose/profiles/): 

```bash
export COMPOSE_PROFILES=<MY_PROFILES>
docker-compose -f docker-compose.yaml up -d --force-recreate --build --no-deps
```

All the application containers (excluding the db -mongo- and the db_seeding -mongo_seed-) are meant to be used for development so docker-compose starts, rather the applications, environments where the development environment of each applications is set up. This means that, to run the application, one has to attach to the container and start it. 

### Example

Here are covered the two most common use case, spinning up the backend and fronted; the new backend and the frontend. 

#### BE and FE

1. Export the COMPOSE_PROFILES:
```bash
export COMPOSE_PROFILES=be,fe
```
2. run docker-compose:
```bash
docker-compose -f docker-compose.yaml up --force-recreate --build --no-deps -d
```

This will start four containers: the be container, the fe one, the mongodb database and a short lived one, called mongodb_seed_be that puts some example data into the be db of mongo.

#### New BE and FE

1. Export the COMPOSE_PROFILES:
```bash
export COMPOSE_PROFILES=be_next,fe
```
2. run docker-compose:
```bash
docker-compose -f docker-compose.yaml up --force-recreate --build --no-deps -d
```

As before, this will start four containers: the be_next container, the fe one, the mongo database and a short lived one, called mongodb_seed_be_next that puts some example data into the be_next db of mongo.

Since the configuration of the frontend with the new backend has slightly changed, remember to set the `accessTokenPrefix` value to "Bearer " in the [config.json](./config/frontend/config.json#L3) file of the fe, before starting the frontend application.
