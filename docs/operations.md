# MPI operations with KubePMIx

### Run with ULFM

KubePMIx works seamlessly with ULFM (the built-in OpenPMIx server handles signal broadcast). There are only requirements for MPI client applications:

- Must be compiled with MPI ULFM (`mpi-ext.h`).
- Must implement failure and shrink of MPI communicator. See [example](https://github.com/kubepmix/images/blob/main/simplempi/app.cpp#L188).
- Must have `OMPI_MCA_mpi_ft_enable` set to `1`.

See [jobset-with-failure-and-shrink.yaml](../test/kubernetes/manifests/jobset-with-failure-and-shrink.yaml) - manifest used in the test framework.

### Monitor modex

KubePMIx logs rank's modex data (MPI rank's endpoint information exchanged via `PMIX_Fence` on MPI client initailization). For example, these pods landed in the pod cidr:

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

See [architecture.md](./architecture.md).
