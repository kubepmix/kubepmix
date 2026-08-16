<p align="center">
  <img src="./docs/kubepmix.svg" />
</p>

# KubePMIx

OpenPMIx server and Kubernetes admission webhook server in one - built to run MPI Jobs on Kubernetes. 

# Quickstart

Make sure [cert-manager](https://cert-manager.io/) is installed on the cluster. Install KubePMIx with Helm Chart:

```
helm -n kubepmix install kubepmix oci://ghcr.io/kubepmix/charts/kubepmix --create-namespace
```

Label Job with `kubepmix.dev/enabled: "true"` to join all replicas to an MPI world:

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
          image: ghcr.io/kubepmix/images/simplempi:latest
```

See how to run [Kubernetes Jobs](docs/jobs.md), [JobSets](docs/jobsets.md), [standalone Pods](docs/pods.md), or [run with docker-compose](docs/compose.md).

# Learn more

See [KubePMIx architecture](docs/architecture.md).
