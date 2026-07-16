# MPI Jobs with KubePMIx

KubePMIx _injects_ MPI context into Kubernetes Job replicas. Works similarly to `mpirun --pernode` - where order doesn't matter.

### Install KubePMIx

To get started, install namespace-scoped KubePMIx:

```bash
export NAMESPACE=myns
helm -n $NAMESPACE install --set=namespaced="true" kubepmix ghcr.io/kubepmix/charts/kubepmix
```

See Helm Chart's [`README.md`](../charts/kubepmix/README.md) for deployment details.

### Deploy Job

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
          image: ghcr.io/kubepmix/simplempi:latest
```

Job replicas will receive consecutive ranks in the order they are created by the Job controller (so no order is guaranteed). Use Kubernetes topology contrains (`nodeSelector`, `nodeAffinity`, etc.) and device configuration (DRA, device plugins) to control number of ranks per node and number of devices and resources attached to each rank.

### See more

To run heterogenous replicas and bind nodes and devices to ranks, see: [Running JobSets](./jobsets.md)
