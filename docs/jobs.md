# MPI Jobs with KubePMIx

KubePMIx _injects_ MPI context into Kubernetes Job replicas. This scenario is desired to cover homogenous parallel jobs, where order of the ranks isn't releveant (similar to `mpirun --pernode`).

### Install KubePMIx

To get started, install namespace-scoped KubePMIx in your namespace:

```bash
export NAMESPACE=myns
helm -n $NAMESPACE install --set scope=Namespace kubepmix ghcr.io/kubepmix/charts/kubepmix
```

See Helm Chart's [`README.md`](../charts/kubepmix/README.md) for deployment details.

### Deploy Job

Label Job with `kubepmix.dev/enabled: "true"` to join all replicas to a the MPI world:

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

Job replicas will receive consecutive ranks in the order they are created by the Job controller (so no order is guaranteed).

### See more

To run heterogenous jobs or bind nodes and devices to ranks, see: [Running JobSets](./jobsets.md)
