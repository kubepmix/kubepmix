# MPI JobSets with KubePMIx

KubePMIx _injects_ MPI context into JobSet Job's replicas. JobSets are useful when different pods must hold different configurations (like environment variables). It's an equivalent for using colon (`:`) in `mpirun`.

### Install KubePMIx

To get started, install KubePMIx:

```bash
helm -n kubepmix install kubepmix oci://ghcr.io/kubepmix/charts/kubepmix --create-namespace
```

See Helm Chart's [`README.md`](../charts/kubepmix/README.md) for deployment details.

### Configure JobSet

KubePMIx is configured by **labelling child jobs** of the JobSet. Each child job must have exactly one replica and have `parallelism` set to 1.

Following labels must be set on every child Job:

- `kubepmix.dev/enabled` - every child job must set this to `"true"`
- `kubepmix.dev/containerRanks` - defined on every child job, comma-separated ranks numbers each container in the pod holds (typically just rank of a single container)

Additionally, one of the Jobs control creation of PMIx Namespace by setting flag and speciyfing size:

- `kubepmix.dev/create` - create namespace
- `kubepmix.dev/size` - size of the namespace to create.

For example:

```
apiVersion: jobset.x-k8s.io/v1alpha2
kind: JobSet
metadata:
  name: jobset
spec:
  replicatedJobs:
    - name: rank0
      replicas: 1
      template:
        metadata:
          labels:
            kubepmix.dev/create: "true"
            kubepmix.dev/size: "2"
            kubepmix.dev/enabled: "true"
            kubepmix.dev/containerRanks: "0" # This job is rank 0
        spec:
          backoffLimit: 0
          parallelism: 1
          completions: 1
          template:
            spec:
              restartPolicy: Never
              terminationGracePeriodSeconds: 0
              containers:
                - name: worker
                  image: ghcr.io/kubepmix/images/simplempi:latest
                  env:
                    - name: "RANK_SPECIFIC_DATA"
                      value: "I am rank 0, yo maan"

                    # Run 1 All Gather
                    - name: GATHER_COUNT
                      value: "1"
                    - name: GATHER_TIME
                      value: "0"
    - name: rank1
      replicas: 1
      template:
        metadata:
          labels:
            kubepmix.dev/enabled: "true"
            kubepmix.dev/containerRanks: "1"
        spec:
          backoffLimit: 0
          parallelism: 1
          completions: 1
          template:
            spec:
              restartPolicy: Never
              terminationGracePeriodSeconds: 0
              containers:
                - name: worker
                  image: ghcr.io/kubepmix/images/simplempi:latest
                  env:
                    - name: "RANK_SPECIFIC_DATA"
                      value: "I will do the job of rank 1"

                    # Run 1 All Gather
                    - name: GATHER_COUNT
                      value: "1"
                    - name: GATHER_TIME
                      value: "0"
```

See: [`test_jobset_explicit_ranks.py`](../test/kubernetes/test_jobset_explicit_ranks.py)

_WARNING:_ There is an unlikely race condition scenario: one of the Pod started and run `MPI_Init()` before the rank 0 job is even admitted (PMIx namespace is not created). To avoid this, gang scheduling enforcement is recommended.

KubePMIx creates an OpenPMIx namespace on every attempt of the JobSet, so pods start over in a fresh namespace every time when JobSet restarts.

### See more

a
See [MPI operations](./operations.md) for fault tolerance (ULFM) and modex monitoring.
