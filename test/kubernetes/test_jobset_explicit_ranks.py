import json
import logging
import pytest
import yaml
from kubernetes import client, dynamic
from conftest import TEST_ID, TEST_NAMESPACE, get_last_log_lines, wait_for_pods_to_complete, inject_test_metadata_to_manifest

log = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def jobset_logs(k8s_client, core_v1):
    manifest_path = "manifests/jobset-with-explicit-ranks.yaml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Inject name, namespace and a job-specific label to the example manifest
    manifest = inject_test_metadata_to_manifest(manifest, TEST_ID, TEST_NAMESPACE)
    
    dyn = dynamic.DynamicClient(k8s_client)
    resource = dyn.resources.get(
        api_version=manifest["apiVersion"],
        kind=manifest["kind"]
    )

    log.info(f"Deploying manifest for test {TEST_ID} from {manifest_path}...")
    resource.create(body=manifest, namespace=TEST_NAMESPACE)

    log.info(f"Waiting for JobSet {TEST_ID} to complete...")
    wait_for_pods_to_complete(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}", expected_count=2, timeout=120)
    parsed_logs = get_last_log_lines(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}")

    yield parsed_logs

    log.info(f"Removing object {TEST_ID}...")
    resource.delete(
        name=TEST_ID,
        namespace=TEST_NAMESPACE
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
