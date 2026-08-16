# MPI jobs with docker-compose

KubePMIx can be used as standalone OpenPMIx server for docker compose MPI workloads. The only caveat is: IP address of the PMIx server must be known in advance, DNS is not supported. See [docker-compose.yaml](../docker-compose.yaml) for a ready-to-use example.

### Server

Add KubePMIx with following configuration::

- `KUBE_PMIX_NAMESPACE_NAME`, `KUBE_PMIX_JOB_SIZE` - Name and size of the namespace to be created on the startup of KubePMIx
- `PMIX_MCA_ptl_*` - OpenPMIx PTL settings to specify the server's endpoint information. KubePMIx reflects all the OpenPMIx MCA settings (as it runs the server underneath).
- `PMIX_MCA_psec` - must be set to `none`

Add healthcheck and optionally set a dedicated PMIx management network:

```yaml
networks:
  # "Management" network - between PMIx server and clients
  pmix-net:
    driver: bridge
    ipam:
      config:
        - subnet: 10.3.0.0/24
  # MPI BTL network - between MPI ranks
  mpi-btl-net:
    driver: bridge
    ipam:
      config:
        - subnet: 10.199.0.0/24

services:
  server:
    image: ghcr.io/kubepmix/kubepmix:latest
    environment:
      # Bootstrap namespace
      KUBE_PMIX_NAMESPACE_NAME: "mynamespace"
      KUBE_PMIX_JOB_SIZE: "2"

      # Fix PMIx server interface and port
      PMIX_MCA_ptl_tcp_ipv4_port: "3333"
      PMIX_MCA_ptl_tcp_if_include: "eth0"

      # Required
      PMIX_MCA_psec: "none" # Do not check processes UID and GUID

    healthcheck:
      test: ["CMD", "python3", "is_healthy.py"]
      start_period: 3s
      interval: 5s
      timeout: 1s
      retries: 5

    networks:
      pmix-net:
        ipv4_address: 10.3.0.10 # Fix address, DNS not supported in pmix server uri
```

### Workers

In your MPI workers, set:

- `PMIX_SERVER_URI2`, `PMIX_NAMESPACE` and `PMIX_RANK` - server and namespace information.
- `PMIX_SECURITY_MODE` - required to be `none`
- `PMIX_GDS_MODULE` - required to be `hash`
- `OMPI_MCA_*` - MPI client's settings, like BTL or fault tolerance settings.

For example:

```yaml
simplempi0:
  image: ghcr.io/kubepmix/images/simplempi:latest
  environment:
    # Rank information - usually set by setup_fork()
    PMIX_SERVER_URI2: "kubepmix.1;tcp4://10.3.0.10:3333"
    PMIX_NAMESPACE: "mynamespace"
    PMIX_RANK: "0"

    # Required
    PMIX_SECURITY_MODE: "none"
    PMIX_GDS_MODULE: "hash"

    # BTL settings
    OMPI_MCA_btl: "tcp,self"
    OMPI_MCA_btl_tcp_if_include: "10.199.0.0/24" # Use mpi-btl-net for MPI communication

    # Application settings, run 5 all gathers with 1 second in between, sleep 5 second
    GATHER_TIME: "1"
    GATHER_COUNT: "5"
    SLEEP_TIME: "1"
    SLEEP_COUNT: "5"

  depends_on:
    server:
      condition: service_healthy
      restart: true # Restart when server restarts

  networks:
    - pmix-net
    - mpi-btl-net
```

Start with:

```bash
docker compose up
```

### See more

Run Kubernetes [Jobs](./jobs.md) and [JobSets](./jobsets.md).
