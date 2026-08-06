# KubePMIx - Architecture

### Overview

KubePMIx is fundamentally an OpenPMIx server, built from official [OpenPMIx Python bindings](https://github.com/openpmix/openpmix/tree/master/bindings), that is wrapped into [Kubernetes Admission Webhook server](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#experimenting-with-admission-webhooks). OpenPMIx namespaces and clients are dynamically registered in the OpenPMIx server, when properly labelled Job or JobSet resource is created on the Kubernetes cluster. Then, pods are mutated with PMIx environment variables generated with `setup_fork()`.

### Motivation

The main motivation of KubePMIx is to be able to run MPI Jobs on Kubernetes cluster, without relying on `mpirun`.

### Role OpenPMIx in MPI jobs

MPI is peer-to-peer in runtime - processes communicate with each other directly, without proxy server. The challenge is to make all the peers aware of each other's endpoints at the process startup. For example, when MPI processes communicate through TCP (TCP Byte-Transfer-Layer is used), each peer needs to know other peers' IP address and port in the network.

When peer process calls `MPI_Init()` - the `PMIx_Fence()` is called. The role of fence is to commit your local endpoint's data to others, and - more importantly - **wait until everyone publishes its endpoint**. When "exchange" is completed - the services flow without the intermediary server. The endpoint exchange must happen through a central OpenPMIx server, which will make sure everyone commited their endpoints before letting everyone continue.

MPI process reads the OpenPMIx server data by reading env vars - `PMIX_SERVER_URI2`, `PMIX_NAMESPACE` and `PMIX_RANK`. This is the only required configuration for MPI process.

In the typical scenario, these env vars are injected by `mpirun` / `prterun`. `prterun` and look like this:

```
PMIX_SERVER_URI2=1856372736.0;tcp4://127.0.0.1:38221
PMIX_NAMESPACE=1839595521
PMIX_RANK=0
```

Indeed every MPI peer launched by `prterun` gets its own **local** OpenPMIx server, accessible via `127.0.0.1`. What `prterun` does is:

- Launches OpenPMIx servers on all the targetted hosts (in )

### Diagram
