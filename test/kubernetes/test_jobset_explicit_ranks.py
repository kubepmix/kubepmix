import json
import logging
import time
import pytest
import yaml
from kubernetes import client, dynamic
from conftest import TEST_ID, TEST_NAMESPACE, get_last_log_lines

log = logging.getLogger(__name__)

def wait_for_finalized_jobset(core_v1, jobset_name, size=4, timeout=120):
    log.info(f"Waiting for jobset {jobset_name} in NS {TEST_NAMESPACE} to complete with timeout {timeout}s...")

    deadline = time.time() + timeout

    while time.time() < deadline:
        pods = core_v1.list_namespaced_pod(
            TEST_NAMESPACE, label_selector=f"jobset.sigs.k8s.io/jobset-name={jobset_name}"
        )
        if pods.items:
            phases = [pod.status.phase for pod in pods.items]
            log.info(f"Waiting for pods to finish, current phases: {phases}")
            if all(phase in ("Succeeded", "Failed") for phase in phases) and len(phases) == size:
                return phases
        time.sleep(0.5)

    pytest.fail(f"JobSet {jobset_name} did not complete within {timeout}s")

@pytest.fixture(scope="module")
def jobset_logs(k8s_client, core_v1):
    manifest_path = "manifests/jobset-with-explicit-ranks.yaml"
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

    log.info(f"Deploying manifest for test {TEST_ID} from {manifest_path}...")
    resource.create(body=manifest, namespace=TEST_NAMESPACE)

    log.info(f"Waiting for JobSet {TEST_ID} to complete...")
    wait_for_finalized_jobset(core_v1, TEST_ID, size=2, timeout=120)
    raw_logs = get_last_log_lines(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}")
    parsed = [json.loads(log) for log in raw_logs]

    yield parsed

    log.info(f"Removing object {TEST_ID}...")
    resource.delete(
        name=TEST_ID,
        namespace=TEST_NAMESPACE,
        body=client.V1DeleteOptions(propagation_policy="Foreground")
    )

def test_all_pods_finished(jobset_logs):
    assert len(jobset_logs) == 2

def test_each_pod_knows_its_rank(jobset_logs):
    for log in jobset_logs:
        assert log.get("myrank") is not None, f"Missing 'myrank' in: {log}"

def test_each_pod_knows_its_hostname(jobset_logs):
    for log in jobset_logs:
        assert log.get("myhostname") is not None, f"Missing 'myhostname' in: {log}"

def test_each_pod_is_mutated_with_pmix_env_vars(jobset_logs):
    for log in jobset_logs:
        env = log.get("myenvs", {})
        assert env.get("PMIX_RANK") is not None, f"Pod was not mutated! Missing PMIX_RANK in: {log}"
        assert env.get("PMIX_NAMESPACE") is not None, f"Pod was not mutated! Missing PMIX_NAMESPACE in: {log}"

def test_there_is_just_one_rank_zero(jobset_logs):
    rank_0_logs = [log for log in jobset_logs if log.get("myrank") == 0]
    assert len(rank_0_logs) == 1, f"Expected exactly one pod with rank 0, found {len(rank_0_logs)}"

def test_each_pod_sees_correct_world_size(jobset_logs):
    for log in jobset_logs:
        assert len(log.get("ranks", [])) == 2, f"Pod just sees itself. Expected 'ranks' length 2 in: {log}"

def test_rank_0_has_rank_specific_data(jobset_logs):
    # Find the log for rank 0
    rank_0_log = next((log for log in jobset_logs if log.get("myrank") == 0), None)
    assert rank_0_log is not None, "No log found for rank 0"
    assert rank_0_log.get("myenvs") is not None, f"Rank 0 log does not contain 'myenvs': {rank_0_log}"

    assert rank_0_log["myenvs"].get("RANK_SPECIFIC_DATA") is not None, f"Rank 0 log does not contain expected 'RANK_SPECIFIC_DATA': {rank_0_log}"
    assert rank_0_log["myenvs"]["RANK_SPECIFIC_DATA"] == "I am rank 0, yo maan", f"Rank 0 log does not contain expected 'RANK_SPECIFIC_DATA' value: {rank_0_log}"
