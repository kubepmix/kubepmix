import logging
import time
import pytest
import yaml
from kubernetes import client, dynamic
from conftest import TEST_ID, TEST_NAMESPACE, get_last_log_lines, wait_for_pods_to_complete, inject_test_metadata_to_manifest, patch_pods_with_finalizer, remove_pods_finalizer

log = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def jobset_logs_with_failing_pod(k8s_client, core_v1):
    manifest_path = "manifests/jobset-with-failure-and-shrink.yaml"
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

    # Sleep for 1s, much more than required for JobSet to create Pods
    time.sleep(1)

    # Patch all the pods with a finalizer - so we can grab the logs before controller kills the pods
    patch_pods_with_finalizer(core_v1, TEST_ID, TEST_NAMESPACE)

    log.info(f"Waiting for JobSet {TEST_ID} to complete...")
    wait_for_pods_to_complete(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}", expected_count=3, timeout=120)
    parsed_logs = get_last_log_lines(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}")
    
    yield parsed_logs

    remove_pods_finalizer(core_v1, TEST_ID, TEST_NAMESPACE)

    log.info(f"Removing object {TEST_ID}...")
    resource.delete(
        name=TEST_ID,
        namespace=TEST_NAMESPACE,
        body=client.V1DeleteOptions(propagation_policy="Foreground")
    )
    
    # Waiting for object to be deleted
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            resource.get(name=TEST_ID, namespace=TEST_NAMESPACE)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                log.info(f"Object {TEST_ID} successfully deleted.")
                break
            else:
                log.warning(f"Unexpected error while checking for deletion of {TEST_ID}: {e}")
        time.sleep(1)
    
    
def test_just_print_log(jobset_logs_with_failing_pod):
    print(f"jobset_logs_with_failing_pod={jobset_logs_with_failing_pod}")
    assert 1 == 1

def test_all_pods_finished(jobset_logs_with_failing_pod):
    assert len(jobset_logs_with_failing_pod) == 3, f"Expected 3 pods, got {len(jobset_logs_with_failing_pod)}"

def test_there_is_one_failed_rank(jobset_logs_with_failing_pod):
    # There is exactly one element of the list with just 'failure' key
    failed_ranks = [log for log in jobset_logs_with_failing_pod if "failure" in log]
    assert len(failed_ranks) == 1, f"Expected 1 failed rank, got {len(failed_ranks)}"

def test_survived_ranks_are_mutated_with_pmix_env_vars(jobset_logs_with_failing_pod):
    for log in jobset_logs_with_failing_pod:
        if "failure" in log:
            continue  # Skip the failed rank
        env = log.get("myenvs", {})
        assert env.get("PMIX_RANK") is not None, f"Pod was not mutated! Missing PMIX_RANK in: {log}"
        assert env.get("PMIX_NAMESPACE") is not None, f"Pod was not mutated! Missing PMIX_NAMESPACE in: {log}"

def test_there_is_just_one_rank_zero_in_survived_ranks(jobset_logs_with_failing_pod):
    surviving_logs = [log for log in jobset_logs_with_failing_pod if "failure" not in log]
    rank_0_logs = [log for log in surviving_logs if log.get("myrank") == 0]
    assert len(rank_0_logs) == 1, f"Expected exactly one pod with rank 0, found {len(rank_0_logs)}"

def test_survived_ranks_know_the_recovery_information(jobset_logs_with_failing_pod):
    for log in jobset_logs_with_failing_pod:
        if "failure" in log:
            continue  # Skip the failed rank
        rank_events = log['events']
        assert len(rank_events) == 1, f"Survived pod does not have the event: {log}"

        recovery_event = rank_events[0]
        assert recovery_event['type'] == 'recovery', f"The event isn't a recovery event: {log}"
        assert recovery_event['size_after'] == recovery_event['size_before'] - 1, f"Invalid size_after in recovery event: {log}"
        assert recovery_event['failed_ranks'] is not None, f"Failed ranks not found: {log}"
        assert len(recovery_event['failed_ranks']) == 1, f"Expected exactly one failed rank in recovery event: {log}"
        assert recovery_event['failed_ranks'][0] == 0, f"Expected failed rank to be 0, got {recovery_event['failed_ranks'][0]} in: {log}"
