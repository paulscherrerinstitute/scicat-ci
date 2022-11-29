# How to get started:

If running on MACOS, because of platform differences, please change the image in the frontend Dockerfile from `node:16-alpine` to `node:16`. 

After that, if needed, build the docker containers with the suitable [profiles](https://docs.docker.com/compose/profiles/): 

```bash
MY_PROFILE=<USER_INPUT>
docker-compose -f docker-compose.yaml --profile $MY_PROFILE up -d --force-recreate --build --no-deps
```
