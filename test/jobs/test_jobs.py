# Basic test that just tests conftest stuff, not real logic
import json
import pytest
from conftest import wait_for_finalized_job, get_last_log_lines

@pytest.mark.parametrize("deploy_manifest", ["manifests/job.yaml"], indirect=True)
def test_job_execution(deploy_manifest):
    job_name, core_v1 = deploy_manifest
    wait_for_finalized_job(core_v1, job_name, size=4, timeout=120)
    last_logs = get_last_log_lines(core_v1, job_name)
    
    assert len(last_logs) == 4, f"Expected 4 log lines, got {len(last_logs)}"
    
    for log in last_logs:
        try:
            log_dict = json.loads(log)
        except json.JSONDecodeError as e:
            pytest.fail(f"Failed to parse log line as JSON: {log}\nError: {e}")
        
        assert log_dict.get("myrank") is not None, f"Log line does not contain 'myrank': {log}"
        assert log_dict.get("myhostname") is not None, f"Log line does not contain 'myhostname': {log}"
        assert len(log_dict.get("ranks")) == 4, f"Expected 'ranks' to have length 4, got {len(log_dict.get('ranks'))} in log: {log}"
