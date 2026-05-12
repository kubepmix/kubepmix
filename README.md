<p align="center">
  <img src="./docs/kubepmix.svg" />
</p>

# KubePMIx

OpenPMIx server and Kubernetes admission webhook in one - built to run MPI Jobs natively on Kubernetes.

# Quickstart

Make sure [cert-manager](https://cert-manager.io/) is installed on the cluster. Install KubePMIx with Helm Chart:

```
helm -n kubepmix install kubepmix ghcr.io/kubepmix/charts/kubepmix --create-namespace
```

Label Job with `kubepmix.dev/enabled: "true"` to join all replicas to a single homogenous MPI world:

```
apiVersion: batch/v1
kind: Job
metadata:
  name: pmix-example
  labels:
    kubepmix.dev/enabled: "true"
spec:
  parallelism: 4
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: worker
          image: ghcr.io/kubepmix/simplempi:latest
```

See: [Running Jobs](docs/jobs.md), [Running JobSets](docs/jobsets.md), [Running PodSets](docs/podsets.md) or [Running with docker-compose](docs/compose.md)

# Learn more

See [architecture.md](docs/architecture.md) for a comprehensive summary.
