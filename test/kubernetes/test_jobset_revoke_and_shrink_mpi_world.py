import json
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
    wait_for_pods_to_complete(core_v1, f"jobset.sigs.k8s.io/jobset-name={TEST_ID}", expected_count=2, timeout=120)
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
    
    
def test_all_pods_finished(jobset_logs_with_failing_pod):
    print(f"jobset_logs_with_failing_pod={jobset_logs_with_failing_pod}")
    assert 1 == 1
