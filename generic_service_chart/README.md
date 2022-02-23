# Generic-service-chart

The idea is to have a chart which is generic enough to be applied to many simple applications. Custom values, like config maps, volumes, env vars and others can be set as values or from file

## TL;DR

```bash
$ helm repo add internal http://melanie.gitpages.psi.ch/templates
$ helm install my-release internal/generic-service-chart
```

## Introduction

This chart bootstraps a generic service deployment on a [Kubernetes](http://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

## Installing the Chart

To install the chart with the release name `my-release`:

```bash
$ helm install my-release internal/generic-service-chart
```

The command deploys a generic service on the Kubernetes cluster in the default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

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

### generic-service-chart parameters

| Parameter                          | Description                                                                                                                              | Default                                                 |
|------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| `image.repository`    | Image name                                                                                                                           | `busybox`                       |
| `image.tag`           | Image tag                                                                                                                            | `latest`                        |
| `image.pullPolicy`    | Image pull policy                                                                                                                    | `Always`                        |
| `run.command`         | Command to be executed by the container                                                                                              | `nil`                           |
| `run.args`            | Arguments to pass the the container command                                                                                          | `nil`                           |
| `env`                 | Envaironment variables to use in the deployment. It follows the same sintax as environment variabels in k8s                          | `[]`                            |
| `volumes`             | Define what volumes to use in the deployment. It follows the same syntax as volumes in k8s                                           | `nil`                           |
| `volumeMounts`        | Define what volumes to mount in the deployment. It follows the same syntax as volumesMounts in k8s                                   | `nil`                           |
| `configMaps`          | Dictionary of `configmapName-> {key:value,}` used to define configmaps. An example `{cm1: {k1:v1,k2:v2}, cm2: {k3:v3}}`              | `{}`                            |
| `test`                | Test to run when using `helm test`. It follows the same syntax as containers in k8s                                                  | `nil` (evaluated as a template) |
| `initialDelaySeconds` | Number of seconds after the container has started before liveness or readiness probes are initiated                                  | `nil`                           |

### Statefulset parameters

| Parameter                   | Description                                                                               | Default                        |
|-----------------------------|-------------------------------------------------------------------------------------------|--------------------------------|
| `replicaCount`              | Number of nodes                                                                           | `1`                            |

### Exposure parameters

| Parameter                            | Description                                                                       | Default                        |
|--------------------------------------|-----------------------------------------------------------------------------------|--------------------------------|
| `service.type`                       | Kubernetes Service type                                                           | `ClusterIP`                    |
| `service.externalPort`               | Service external port                                                             | `3000`                         |
| `service.internalPort`               | Service internal port name                                                        | `80`                           |
| `ingress.enabled`                    | Enable ingress resource for Management console                                    | `false`                        |
| `ingress.hosts[0].host`              | Host                                                                              | `nil`                          |
| `ingress.hosts[0].paths[0].path`     | Path for the default host                                                         | `/`                            |
| `ingress.hosts[0].tls[0].secretName` | Name of existing secret contiaining the tls certificate                           | `nil`                          |
| `ingress.hosts[0].tls[0].hosts[0]`   | Host on which to apply the tls encription                                         | `nil`                          |

Specify each parameter using the `--set key=value[,key=value]` or `--set-file key=value[,key=value]` argument to `helm install`. For example,

```bash
$ helm install my-release \
  --set configMaps.cm.key=value \
  --set-file configMaps.cm.key1=path_to_file \
    internal/generic-service-chart
```

The above command sets and creates a configmap, named cm, with two values: one with key `key` and value `value` and the second with key `key1` and value equal to the content of the file in `path_to_file`.

> **Tip**: You can use the default [values.yaml](values.yaml)

## Configuration and installation details

### Define helm tests

To set the test to run, define this command:
```bash
$ TESTCASE=`cat << EOF
containers:
  - name: wget
    image: busybox
    command: ['wget']
    args: ['{{ include "helm_chart.fullname" . }}:{{ .Values.service.externalPort }}']
EOF`
$ helm install my-release \
  --set test=$TESTCASE
$ helm test my-release
```

### Scale horizontally

To horizontally scale this chart once it has been deployed, two options are available:

- Use the `kubectl scale` command.
- Upgrade the chart modifying the `replicaCount` parameter.
