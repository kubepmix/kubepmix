# MPI Jobs with KubePMIx

KubePMIx _injects_ MPI context into Kubernetes Job replicas.

### Install KubePMIx

To get started, install KubePMIx:

```bash
helm -n kubepmix install kubepmix oci://ghcr.io/kubepmix/charts/kubepmix --create-namespace
```

See Helm Chart's [`README.md`](../charts/kubepmix/README.md) for deployment details.

### Deploy Job

Label Job with `kubepmix.dev/enabled: "true"`:

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

Job replicas will receive consecutive ranks in the order they are intercepted by admission webhook - so no order is guaranteed. Use Kubernetes topology contrains (`nodeSelector`, `nodeAffinity`, etc.) and device configuration (DRA, device plugins) to control number of ranks per node and number of devices and resources attached to each rank.

### See more

To run heterogenous replicas and bind nodes to ranks, see: [Running JobSets](./jobsets.md)
