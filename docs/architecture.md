# KubePMIx - Architecture

### Overview

KubePMIx is fundamentally an OpenPMIx server, built from official [OpenPMIx Python bindings](https://github.com/openpmix/openpmix/tree/master/bindings), that is wrapped into [Kubernetes Admission Webhook server](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#experimenting-with-admission-webhooks). OpenPMIx namespaces and clients are dynamically registered in the OpenPMIx server, when properly labelled Job or JobSet resource is created on the Kubernetes cluster. Then, pods are mutated with PMIx environment variables generated with `setup_fork()`.

### Motivation

The main motivation of KubePMIx is to be able to run MPI Jobs on Kubernetes cluster, without relying on `mpirun`.

### Role OpenPMIx in MPI jobs

MPI is peer-to-peer at runtime — processes communicate with each other directly, without any intermediary proxy server. The one prerequisite this imposes is that every process must exchange its endpoint information with all peers, so that direct peer-to-peer connections can be established.

For example, when MPI processes communicate over TCP (using the TCP Byte-Transfer-Layer), each peer needs to know the IP address and port of every other peer on the network.

When a peer process initializes itself in the MPI world (calls `MPI_Init()`), it invokes `PMIx_Fence()` underneath. The role of the fence is to publish your local endpoint data to the others and — more importantly — to **wait until every peer has published its own endpoint**. Once this collective exchange completes, communication flows directly between peers, with no intermediary server involved. The exchange itself, however, must go through a central OpenPMIx server, which guarantees that all processes have committed their endpoints before any of them is allowed to proceed.

MPI process reads the OpenPMIx server data by reading env vars - `PMIX_SERVER_URI2`, `PMIX_NAMESPACE` and `PMIX_RANK`. This is the only required configuration for MPI process.

In the typical scenario, these env vars are injected by `mpirun` / `prterun`. `prterun` and look like this:

```
PMIX_SERVER_URI2=1856372736.0;tcp4://127.0.0.1:38221
PMIX_NAMESPACE=1839595521
PMIX_RANK=0
```

Indeed every MPI peer launched by `prterun` gets its own **local** OpenPMIx server, accessible via `127.0.0.1`. These servers are launched on every target node of the `prterun` job, usually using SSH.

In summary, `prte`:

- Launches OpenPMIx servers on all targeted hosts (via the PLM)
- Starts each process with a mutated environment (including `PMIX_SERVER_URI2`)

For the MPI client, KubePMIx plays the same role that prted plays under normal circumstances: it is the local server that enables `PMIx_Fence()` to run. All the Fence logic is included in OpenPMIx.

### Diagram

<p align="center">
  <img src="./diagram.png" />
</p>
