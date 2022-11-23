# How to get started:

If running on MACOS, because of platform differences, please change the image in the frontend Dockerfile from `node:16-alpine` to `node:16`. 

After that, if needed, build the docker containers with the suitable profiles: 

```bash
docker-compose -f docker-compose.dev.yaml --profile legacy up -d --force-recreate --build --no-deps
```
