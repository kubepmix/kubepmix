# MPI Jobs with KubePMIx

KubePMIx _injects_ MPI context into Kubernetes Job replicas

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

KubePMIx will create the MPI world of 4 (as specified in `parallelism`). Job replicas will receive consecutive as they're intercepted by admission webhook - so no order is guaranteed. Use Kubernetes topology contrains (`nodeSelector`, `nodeAffinity`, etc.) and device configuration (DRA, device plugins) to control number of ranks per node and number of devices and resources attached to each rank.

### Monitor modex

KubePMIx logs rank's modex data (MPI rank's endpoint information [BTL] exchanged via `PMIX_Fence` on MPI client initailization), for example, these pods landed in the pod cidr:

```
[ ns | 0 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '10.42.1.216', 'port': 1024, 'family': 'IPv4', 'ifkindex': 2, 'mask': 24, 'bandwidth_mbps': 10000}]}
[ ns | 2 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '10.42.1.217', 'port': 1024, 'family': 'IPv4', 'ifkindex': 2, 'mask': 24, 'bandwidth_mbps': 10000}]}
```

BTL data might contain more interfaces, for example, for my setup with `hostNetwork: true` I see:

```
[ ns | 2 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '<my-public-ip>', 'port': 1025, 'family': 'IPv4', 'ifkindex': 2, 'mask': 32, 'bandwidth_mbps': 100}, {'ip': '10.42.1.0', 'port': 1025, 'family': 'IPv4', 'ifkindex': 3, 'mask': 32, 'bandwidth_mbps': 100}, {'ip': '10.42.1.1', 'port': 1025, 'family': 'IPv4', 'ifkindex': 4, 'mask': 24, 'bandwidth_mbps': 10000}]}
[ ns | 0 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '<my-public-ip>', 'port': 1027, 'family': 'IPv4', 'ifkindex': 2, 'mask': 32, 'bandwidth_mbps': 100}, {'ip': '10.42.1.0', 'port': 1027, 'family': 'IPv4', 'ifkindex': 3, 'mask': 32, 'bandwidth_mbps': 100}, {'ip': '10.42.1.1', 'port': 1027, 'family': 'IPv4', 'ifkindex': 4, 'mask': 24, 'bandwidth_mbps': 10000}]}
```

BTL TCP interface can be set by `OMPI_MCA_btl_tcp_if_include` on the client. For example, when setting it to `lo` ony my kind setup:

```
[ ns | 1 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '127.0.0.1', 'port': 1025, 'family': 'IPv4', 'ifkindex': 1, 'mask': 8, 'bandwidth_mbps': 100}]}
[ ns | 0 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '127.0.0.1', 'port': 1026, 'family': 'IPv4', 'ifkindex': 1, 'mask': 8, 'bandwidth_mbps': 100}]}
[ ns | 3 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '127.0.0.1', 'port': 1024, 'family': 'IPv4', 'ifkindex': 1, 'mask': 8, 'bandwidth_mbps': 100}]}
[ ns | 2 ] Registered Modex: {'btl.tcp.5.0': [{'ip': '127.0.0.1', 'port': 1027, 'family': 'IPv4', 'ifkindex': 1, 'mask': 8, 'bandwidth_mbps': 100}]}
```

_WARNING_: For other BTLs / PMLs, the verbosity will be limited, PRs welcome.

### See more

To run heterogenous replicas and bind nodes to ranks, see: [Running JobSets](./jobsets.md)
