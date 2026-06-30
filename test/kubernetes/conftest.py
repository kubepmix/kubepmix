import pytest
import json
import os
import logging
from kubernetes import client, config, dynamic
import yaml

log = logging.getLogger(__name__)


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

def inject_test_metadata_to_manifest(manifest, test_id, test_namespace):
    # Inject name and namespace
    manifest["metadata"]["name"] = test_id
    manifest["metadata"]["namespace"] = test_namespace

    # Inject a special label for the test, append if exists
    if "labels" in manifest["metadata"]:
        manifest["metadata"]["labels"]["ci.kubepmix.dev/test-id"] = test_id
    else:
        manifest["metadata"]["labels"] = {"ci.kubepmix.dev/test-id": test_id}

    # If the manifest has replicated jobs (it's a jobset), inject labels into each job template
    for job in manifest.get("spec", {}).get("replicatedJobs", []):
        job["template"]["metadata"]["labels"]["ci.kubepmix.dev/test-id"] = test_id
        job["template"]["spec"]["template"]["metadata"] = {"labels": {"ci.kubepmix.dev/test-id": test_id}}

    # If it's a job, inject labels into the pod template
    if "replicatedJobs" not in manifest.get("spec", {}):
        if "spec" in manifest and "template" in manifest["spec"]:
            manifest["spec"]["template"]["metadata"] = {"labels": {"ci.kubepmix.dev/test-id": TEST_ID}}

    return manifest

# Read last log of all of the pods from the job.
# Last log is expected to be in the special form of dict returned from jjlakis/simplempi image
def get_last_log_lines(core_v1, label_selector):
    pods = core_v1.list_namespaced_pod(
        TEST_NAMESPACE, label_selector=label_selector
    )

    if not pods.items:
        pytest.fail(f"No pods found for label selector {label_selector}")

    last_logs = []
    for pod in pods.items:
        log_response = core_v1.read_namespaced_pod_log(pod.metadata.name, TEST_NAMESPACE, _preload_content=False)
        try:
            log = log_response.data.decode("utf-8")
            last_logs.append(log.strip().splitlines()[-1])
        except Exception as e:
            pytest.fail(f"Failed to parse logs for pod {pod.metadata.name}: {e}")

    return last_logs


def wait_for_pods_to_complete(core_v1, label_selector, expected_count, timeout=120):
    import time
    deadline = time.time() + timeout

    while time.time() < deadline:
        pods = core_v1.list_namespaced_pod(
            TEST_NAMESPACE, label_selector=label_selector
        )
        if len(pods.items) == expected_count:
            phases = [pod.status.phase for pod in pods.items]
            if all(phase in ("Succeeded", "Failed") for phase in phases):
                return phases
        time.sleep(0.5)

    pytest.fail(f"Pods with label selector {label_selector} did not complete within {timeout}s")
    
