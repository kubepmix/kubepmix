# MPI jobs with docker-compose

KubePMIx can be used as standalone OpenPMIx server for container workloads.

### Usage

Add KubePMIx to docker-compose.yaml:

```
  server:
    image: ghcr.io/kubepmix/kubepmix:latest
    environment:
      #
      KUBE_PMIX_SERVER_PORT: "3333"
      KUBE_PMIX_SERVER_IFACE: "eth0"

      # Required - do not check processes UID and GUID
      PMIX_MCA_psec: "none"

      # Namespace bootstrap
      KUBE_PMIX_NAMESPACE_NAME: "my-pmix-namespace"
      KUBE_PMIX_JOB_SIZE: "2"
    networks:
      kube-pmix-net:
        ipv4_address: 10.3.0.10 # We fix address, DNS not supported in pmix server uri
```
