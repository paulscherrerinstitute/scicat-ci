# Cron-chart

A simple chart to deploy a cronJob runner mounting secrets

## Installing the Chart

To install the chart with the release name `my-release`:

```bash
$ helm install my-release cron_chart
```

The command deploys a cron chart on the Kubernetes cluster in the default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

> **Tip**: List all releases using `helm list`

## Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
$ helm delete my-release
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

## Parameters

The following table lists the configurable parameters of the chart and their default values.

### Common parameters

| Parameter           | Description                                                          | Default                        |
|---------------------|----------------------------------------------------------------------|--------------------------------|
| `nameOverride`      | String to partially override fullname                                | `nil`                          |
| `fullnameOverride`  | String to fully override fullname                                    | `nil`                          |

### cron-chart parameters

| Parameter                          | Description                                                                                                                              | Default                                                 |
|------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| `image.repository`    | Image name                                                                                                                           | `busybox`                       |
| `image.tag`           | Image tag                                                                                                                            | `latest`                        |
| `image.pullPolicy`    | Image pull policy                                                                                                                    | `Always`                        |
| `cronjob.restartPolicy`         | Set the cronjob restart policy                                                                                              | `OnFailure`                           |
| `cronjob.schedule`            | Set the schedule of the cronjob in the usual cron format command                                                                                          | `0 7 * * 1`                           |
| `cronjob.secret` | Name of the secret used by the cronjob to fetch env vars                                  | `nil`                           |
| `secrets` | Object of objects which create secrets, in the form: { secretName:{ type:Opaque,data:{ key1:value1,key2:value2,key3:value3 } } }
                                  | `nil`                           |
| `volumes` | Object of arrays with volumes to mount, in the form: https://kubernetes.io/docs/concepts/storage/volumes/#background | `nil`                           |
| `volumeMounts` | Object of arrays with volumes to mount and where, in the form: https://kubernetes.io/docs/concepts/storage/volumes/#background | `nil`                           |
