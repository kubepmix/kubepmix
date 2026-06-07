import json
import pytest
import yaml
from kubernetes import client, utils, dynamic
from conftest import TEST_ID, wait_for_finalized_job, get_last_log_lines


@pytest.fixture(scope="module")
def job_logs(k8s_client, core_v1):
    manifest_path = "manifests/job.yaml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    manifest["metadata"]["namespace"] = TEST_ID
    
    print(f"Deploying manifest for test {TEST_ID} from {manifest_path}...")
    utils.create_from_dict(k8s_client, manifest)
    job_name = manifest["metadata"]["name"]

    print(f"Waiting for Job {job_name} to complete...")
    wait_for_finalized_job(core_v1, job_name, size=4, timeout=120)
    raw_logs = get_last_log_lines(core_v1, job_name)
    parsed = [json.loads(log) for log in raw_logs]

    yield parsed

    dyn = dynamic.DynamicClient(k8s_client)
    resource = dyn.resources.get(
        api_version=manifest["apiVersion"],
        kind=manifest["kind"]
    )
    print(f"Removing object {job_name}...")
    resource.delete(
        name=job_name,
        namespace=TEST_ID,
        body=client.V1DeleteOptions(propagation_policy="Foreground")
    )

def test_log_count(job_logs):
    assert len(job_logs) == 4

def test_log_has_myrank(job_logs):
    for log in job_logs:
        assert log.get("myrank") is not None, f"Missing 'myrank' in: {log}"


def test_log_has_myhostname(job_logs):
    for log in job_logs:
        assert log.get("myhostname") is not None, f"Missing 'myhostname' in: {log}"


def test_log_ranks_length(job_logs):
    for log in job_logs:
        assert len(log.get("ranks", [])) == 4, f"Expected 'ranks' length 4 in: {log}"

def test_pmix_env_vars_set(job_logs):
    for log in job_logs:
        env = log.get("myenvs", {})
        assert env.get("PMIX_RANK") is not None, f"Missing PMIX_RANK in: {log}"
        assert env.get("PMIX_NAMESPACE") is not None, f"Missing PMIX_NAMESPACE in: {log}"