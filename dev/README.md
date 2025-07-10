# Local Development

## Overview

Development can be done running local docker containers. First `docker compose` is used
to launch containers for each service. Most containers do not start the service
directly, allowing this to be done manually from inside the container (eg using VS Code
Dev Containers). Commands for each service are given below.

## Clone the repo and the submodules

```bash
git clone git@github.com:paulscherrerinstitute/scicat-ci.git
git submodule update --init --recursive --remote
```

## Starting containers

### :warning: IMPORTANT
The `docker compose` builds the containers from the Dockerfile of each submodule, thus
using the submodule checked out to a particular commit. It is often the case that when
setting up the environment one wants the components to be checked out automatically to
the latest on main. The command above (`git submodule update --init --recursive
--remote`) does that but might break any component where a non-backwards compatible
change was applied. We reference in the config of each components the latest commit
(.git-commit-sha) of the submodule where `docker compose` was run and worked the last
time, whenever the submodule commit is different from the one referenced in the
scicat-ci repo.

To build a container based on a different commit one has to checkout first the submodule
to the commit (or branch) of interest.

Build the docker containers with the suitable
[profiles](https://docs.docker.com/compose/profiles/):

```bash
export COMPOSE_PROFILES=<MY_PROFILES>
docker compose -f docker-compose.yaml up -d --force-recreate --build --no-deps
```

All the application containers (excluding the db -mongo- and the db_seeding
-mongo_seed-) are meant to be used for development so `docker compose` starts, rather than
the applications, environments where the development environment of each application is
set up. This means that, to run the application, one has to attach to the container and
start it.

### Examples

Here are the two most common use cases, spinning up the backend and fronted; the new
backend and the frontend.

#### BE and FE

1. Export the COMPOSE_PROFILES:
```bash
export COMPOSE_PROFILES=be,fe
```
2. run docker compose:
```bash
docker compose -f docker-compose.yaml up --force-recreate --build --no-deps -d
```

This will start four containers: the be container, the fe one, the mongodb database and
a short-lived one, called mongodb_seed_be that puts some example data into the be db of
mongo.

#### New BE and FE

1. Export the COMPOSE_PROFILES:
```bash
export COMPOSE_PROFILES=be_next,fe
```
2. run docker compose:
```bash
docker compose -f docker-compose.yaml up --force-recreate --build --no-deps -d
```

As before, this will start four containers: the be_next container, the fe one, the mongo
database and a short-lived one, called mongodb_seed_be_next that puts some example data
into the be_next db of mongo.

Since the configuration of the frontend with the new backend has slightly changed,
remember to set the `accessTokenPrefix` value to "Bearer " in the
[config.json](./config/frontend/config.json#L3) file of the fe, before starting the
frontend application.


## Starting services

The `docker-compose.yaml` file is constructed to prepare containers with all
dependencies but not to start the services. This is generally done by overriding the
command with an infinite loop.

### Backend `be`

```bash
cd /home/node/app
npm start
```

### Backend-next `be_next`

```bash
cd /home/node/app
npm start:dev
```

The swagger API will be available at
[http://127.0.0.1:3000/explorer](http://127.0.0.1:3000/explorer).

For development you can also start with live file monitoring using the command:

```sh
npm run start:dev
```

Note that configuration occurs through environment variables within the container.
Defaults are populated from `config/backend_next/.env` when the container is built, but
can be overridden at runtime within the container or by mounting a `.env` file at
`/home/node/app/.env`.
The `jobConfig.yaml` file is mounted from `dev/config/backend_next/jobConfig.yaml`. This container is intended for development.

### Test backend-next `test_be_next`

```bash
cd /home/node/app
npm run start:dev
# in another shell
npm run
```

This container is intended for running api tests. It uses a different database than
`be_next`. Functional accounts and jobs are taken from the test configurations in the
scicat-backend-next repository.

### Frontend `fe`

The frontend uses a custom Dockerfile with the following modifications:

```bash
cd /frontend
npm start -- --host 0.0.0.0 --disable-host-check
```

The frontend will be available at [http://127.0.0.1:4200/](http://127.0.0.1:4200/).

A custom Dockerfile is used because the production image uses the node alpine base image
which does not cross-compile on macOS. Additionally, the production image builds the
static site and then serves it via nginx. The development image serves the site using
`ng serve` (webpack-dev-server) so it reflects the latest code and updates when files
change.

### Search `search`

```
cd /home/node/app
npm start
```

The PANOSC search API will be available at
[localhost:3002/explorer/](localhost:3002/explorer/).

### Landing Page `lp`

```bash
cd /home/node/app
npm start -- --host 0.0.0.0 --disable-host-check
```

The DOI landing page will be available at
[http://localhost:4201/](http://localhost:4201/).


### OAI-PMH `oi`

```bash
cd /home/node/app
npm start
```

Or for development,

```sh
npm run dev
```

The OAI-PMG landing page will be available at
[http://localhost:3001/](http://localhost:3001/).


### Proposals `pr`

```bash
cd /usr/src/proposals
python src/main.py
```

### Jupyter

Simply browse to localhost:8888

### RabbitMQ

RabbitMQ can be started by including rabbitmq in the profiles, eg `COMPOSE_PROFILES=be_next,rabbitmq`.
The management console can be accessed at http://localhost:15672.

The `be_next` configuration files need to be modified to reach RABBITMQ. In
`backend_next/.env` set `RABBITMQ_ENABLED=yes`. You may want to update the password as
well, both there and in `rabbitmq/.env`. After this rabbitmq actions can be added to
`jobConfig.yaml` on the backend.

## Reclaiming space

This compose file creates a new docker volume with test data. Removing this requires
adding `--volumes` when shutting down the containers:

```bash
docker compose -f docker-compose.yaml down --volumes
```

If this is omitted it may eventually lead to your docker virtual disk filling up. If
this happens, remove old volumes:

```bash
docker volume prune
docker system prune -v
```
