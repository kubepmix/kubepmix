# MPI JobSets with KubePMIx

KubePMIx _injects_ MPI context into JobSet Job's replicas. JobSets are useful in the scenarios where different pods must hold different configurations (like environment variables). It's an equivalent for using colon (`:`) in `mpirun`.

### Install KubePMIx

To get started, install KubePMIx:

```bash
helm -n kubepmix install kubepmix oci://ghcr.io/kubepmix/charts/kubepmix --create-namespace
```

See Helm Chart's [`README.md`](../charts/kubepmix/README.md) for deployment details.

### Configure JobSet

KubePMIx is configured by **labelling child jobs** of the JobSet. Each child job must have exactly one replica and have `parallelism` set to 1.

Following labels are supported:

-

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
            kubepmix.dev/enabled: "true"
            kubepmix.dev/create: "true"
            kubepmix.dev/size: "2"
            kubepmix.dev/containerRanks: "0"
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
                  image: ghcr.io/jjlakis/simplempi:0.6.0
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
                  image: ghcr.io/jjlakis/simplempi:0.6.0
                  env:
                    - name: "RANK_SPECIFIC_DATA"
                      value: "I will do the job of rank 1"

                    # Run 1 All Gather
                    - name: GATHER_COUNT
                      value: "1"
                    - name: GATHER_TIME
                      value: "0"
```
