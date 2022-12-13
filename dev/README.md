# How to get started:

Build the docker containers with the suitable [profiles](https://docs.docker.com/compose/profiles/): 

```bash
MY_PROFILE=<USER_INPUT>
docker-compose -f docker-compose.yaml --profile $MY_PROFILE up -d --force-recreate --build --no-deps
```
