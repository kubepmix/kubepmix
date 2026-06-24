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
