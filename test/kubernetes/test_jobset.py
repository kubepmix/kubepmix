import json
import time
import pytest
import yaml
from kubernetes import client, dynamic
from conftest import TEST_ID, TEST_NAMESPACE, get_last_log_lines

def wait_for_finalized_jobset(core_v1, jobset_name, size=4, timeout=120):
    print(f"Waiting for jobset {jobset_name} in NS {TEST_NAMESPACE} to complete with timeout {timeout}s...")

    deadline = time.time() + timeout

    while time.time() < deadline:
        pods = core_v1.list_namespaced_pod(
            TEST_NAMESPACE, label_selector=f"jobset.sigs.k8s.io/jobset-name={jobset_name}"
        )
        if pods.items:
            phases = [pod.status.phase for pod in pods.items]
            print(f"Waiting for pods to finish, current phases: {phases}")
            if all(phase in ("Succeeded", "Failed") for phase in phases) and len(phases) == size:
                return phases
        time.sleep(0.5)

    pytest.fail(f"JobSet {jobset_name} did not complete within {timeout}s")

@pytest.fixture(scope="module")
def job_logs(k8s_client, core_v1):
    manifest_path = "manifests/jobset.yaml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Inject name, namespace and a job-specific label to the example manifest
    manifest["metadata"]["name"] = TEST_ID
    manifest["metadata"]["namespace"] = TEST_NAMESPACE
    manifest["metadata"]["labels"] = {"ci.kubepmix.dev/test-id": TEST_ID}
    for job in manifest.get("spec", {}).get("replicatedJobs", []):
        job["template"]["metadata"]["labels"]["ci.kubepmix.dev/test-id"] = TEST_ID
        job["template"]["spec"]["template"]["metadata"] = {"labels": {"ci.kubepmix.dev/test-id": TEST_ID}}

    # JobSet is a CRD, so utils.create_from_dict() can't resolve a typed API
    # class for it (it would look for a non-existent JobsetX-k8sIoV1alpha2Api).
    # The dynamic client works for any resource kind, including CRDs.
    dyn = dynamic.DynamicClient(k8s_client)
    resource = dyn.resources.get(
        api_version=manifest["apiVersion"],
        kind=manifest["kind"]
    )

    print(f"Deploying manifest for test {TEST_ID} from {manifest_path}...")
    resource.create(body=manifest, namespace=TEST_NAMESPACE)

    print(f"Waiting for JobSet {TEST_ID} to complete...")
    wait_for_finalized_jobset(core_v1, TEST_ID, size=2, timeout=120)
    raw_logs = get_last_log_lines(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}")
    parsed = [json.loads(log) for log in raw_logs]

    yield parsed

    print(f"Removing object {TEST_ID}...")
    resource.delete(
        name=TEST_ID,
        namespace=TEST_NAMESPACE,
        body=client.V1DeleteOptions(propagation_policy="Foreground")
    )

def test_just_print(job_logs):
    print(job_logs)
    pass
