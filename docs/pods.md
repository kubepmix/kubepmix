# MPI jobs with standalone Pods

KubePMIx can be used as a standalone OpenPMIx server for arbitrary Kubernetes pods - managed by a human or preferably a Kubernetes operator. The OpenPMIx server can be bootstrapped with a namespace that can be further consumed by the worker ranks.

Operator is responsible for:

- Creating OpenPMIx server
- Assigning / retrieving OpenPMIx server's IP
- Set PMIx server information into the worker pods.

In the following example, we fix the IP by using Kubernetes service.

### Server deployment

Namespace bootstrapping is configured by `KUBE_PMIX_NAMESPACE_NAME` and `KUBE_PMIX_JOB_SIZE`. Port is fixed by OpenPMIx MCA settings.

```
apiVersion: v1
kind: Pod
metadata:
  name: kubepmix-server
  labels:
    app: kubepmix-server
spec:
  containers:
    - name: server
      image: ghcr.io/kubepmix/kubepmix:latest
      ports:
        - name: pmix-ptl
          containerPort: 3333
      env:
        # Bootstrap namespace
        - name: KUBE_PMIX_NAMESPACE_NAME
          value: "mynamespace"
        - name: KUBE_PMIX_JOB_SIZE
          value: "2"
        # Fix PMIx server interface and port
        - name: PMIX_MCA_ptl_tcp_ipv4_port
          value: "3333"
        - name: PMIX_MCA_ptl_tcp_if_include
          value: "eth0"
        # Required
        - name: PMIX_MCA_psec
          value: "none" # Do not check processes UID and GUID
      livenessProbe:
        exec:
          command: ["python3", "is_healthy.py"]
        initialDelaySeconds: 1
        periodSeconds: 5
        timeoutSeconds: 1
        failureThreshold: 5
      readinessProbe:
        exec:
          command: ["python3", "is_healthy.py"]
        initialDelaySeconds: 1
        periodSeconds: 5
        timeoutSeconds: 1
        failureThreshold: 5
```

We also create a service with fixed IP:

```
apiVersion: v1
kind: Service
metadata:
  name: kubepmix
spec:
  selector:
    app: kubepmix-server
  ports:
    - name: pmix-ptl
      port: 3333
  clusterIP: 10.43.43.43
```

### Workers deployment

Workers must have `PMIX_SERVER_URI2` set to our server endpoint, have `PMIX_NAMESPACE` matching our bootstrapped namespace name, and `PMIX_RANK` with desired rank + some other required envs:

```
apiVersion: v1
kind: Pod
metadata:
  name: rank0
  labels:
    app: rank0
spec:
  restartPolicy: Never
  containers:
    - name: rank0
      image: ghcr.io/kubepmix/images/simplempi:latest
      env:
        - name: PMIX_SERVER_URI2
          value: "kubepmix.1;tcp4://10.43.43.43:3333" # prefix is always kubepmix.1
        - name: PMIX_NAMESPACE
          value: "mynamespace"
        - name: PMIX_RANK
          value: "0"
        # Required
        - name: PMIX_SECURITY_MODE
          value: "none"
        - name: PMIX_GDS_MODULE
          value: "hash"
        # Application settings, run 5 all gathers with 1 second in between, sleep 5 second
        - name: GATHER_TIME
          value: "1"
        - name: GATHER_COUNT
          value: "5"
        - name: SLEEP_TIME
          value: "1"
        - name: SLEEP_COUNT
          value: "5"
```

### See more

Run Kubernetes [Jobs](./jobs.md), [JobSets](./jobsets.md) and see [Architecture](./architecture.md).
