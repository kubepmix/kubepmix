import pytest
import os
from kubernetes import client, config

# Test ID is both NS name and release name, must be unique across all tests
TEST_ID=os.getenv("TEST_ID", "test-job")
TEST_NAMESPACE=os.getenv("TEST_NAMESPACE", "ci")

def pytest_configure():
    try:
        config.load_kube_config()
    except config.config_exception.ConfigException:
        config.load_incluster_config()

@pytest.fixture(scope="session")
def k8s_client():
    return client.ApiClient()

@pytest.fixture(scope="session")  
def core_v1(k8s_client):
    return client.CoreV1Api(k8s_client)

# Read last log of all of the pods from the job.
# Last log is expected to be in the special form of dict returned from jjlakis/simplempi image
def get_last_log_lines(core_v1, job_name):
    pods = core_v1.list_namespaced_pod(
        TEST_NAMESPACE, label_selector=f"job-name={job_name}"
    )

    if not pods.items:
        pytest.fail(f"No pods found for job {job_name}")

    last_logs = []
    for pod in pods.items:
        log_response = core_v1.read_namespaced_pod_log(pod.metadata.name, TEST_NAMESPACE, _preload_content=False)
        try:
            log = log_response.data.decode("utf-8")
            last_logs.append(log.strip().splitlines()[-1])
        except Exception as e:
            pytest.fail(f"Failed to parse logs for pod {pod.metadata.name}: {e}")

    return last_logs
