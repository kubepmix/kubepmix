## Developing tests

Install chart from `charts/kubepmix`:

```
helm -ntest-development install --create-namespace kubepmix -f values.yaml --set=namespaced="true" .
```

Now run tests:

```
source ../venv/bin/activate
export TEST_NAMESPACE=test-development
export TEST_ID=mytest123
pytest -sv
```

### JobSet finalizers

To prevent JobSet from deleting pods (cause we have to read logs), for example:

```
# Start JobSet with failure and shrink
kubectl -ntest-development create -f jobset-with-failure-and-shrink.yaml

# Patch all pods with jobset name set as label with a finalizer
kubectl -n test-development get pods -l jobset.sigs.k8s.io/jobset-name=jobset -o name | \
    xargs -I{} kubectl -n test-development patch {} -p '{"metadata":{"finalizers":["test.kubepmix.dev/keep-for-logs"]}}'


## Run tests, collect logs etc etc etc....
kubectl -ntest-development delete -f jobset-with-failure-and-shrink.yaml

# Empty the finalizer
kubectl -n test-development get pods -l jobset.sigs.k8s.io/jobset-name=jobset -o name | \
  xargs -I{} kubectl -n test-development patch {} --type=json -p '[{"op":"remove","path":"/metadata/finalizers"}]'

# Pods should die without explicit delete as they have deletionTimestamp from Job controller...

(Above is already [implemented](kubernetes/test_jobset_revoke_and_shrink_mpi_world.py))
```
