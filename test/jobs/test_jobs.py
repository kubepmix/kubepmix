import pytest
import time
import yaml
from kubernetes import client, config, utils, dynamic

def pytest_configure(config):
    config.load_incluster_config()

@pytest.fixture(scope="session")
def k8s_client():
    return client.ApiClient()


@pytest.fixture(scope="session")  
def core_v1(k8s_client):
    return client.CoreV1Api(k8s_client)

@pytest.fixture(scope="function")
def deploy_manifest(k8s_client, core_v1, request):
    manifest_path = request.param
    namespace = "default"

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    utils.create_from_yaml(k8s_client, manifest_path)
    job_name = manifest["metadata"]["name"]

    yield job_name, core_v1, namespace

    # Teardown — always runs
    dyn = dynamic.DynamicClient(k8s_client)
    resource = dyn.resources.get(
        api_version=manifest["apiVersion"],
        kind=manifest["kind"]
    )
    resource.delete(name=job_name, namespace=namespace)


def wait_for_finalized(core_v1, job_name, namespace, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pods = core_v1.list_namespaced_pod(
            namespace, label_selector=f"job-name={job_name}"
        )
        if pods.items:
            phase = pods.items[0].status.phase
            if phase in ("Succeeded", "Failed"):
                return phase
        time.sleep(2)
    pytest.fail(f"Job {job_name} did not complete within {timeout}s")


def get_last_log_line(core_v1, job_name, namespace):
    pods = core_v1.list_namespaced_pod(
        namespace, label_selector=f"job-name={job_name}"
    )
    pod_name = pods.items[0].metadata.name
    log = core_v1.read_namespaced_pod_log(pod_name, namespace)
    return log.strip().splitlines()[-1]
