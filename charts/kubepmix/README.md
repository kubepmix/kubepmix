# KubePMIx - Helm Chart

KubePMIx - OpenPMIx server & Kubernetes admission webhook in one - built to run MPI jobs natively on Kubernetes.

### Created resources

- `cert.yaml.tpl` - cert-manager-manager certificate for admission webhook
- `server.yaml.tpl` - KubePMIx deployment
- `webhook.yaml.tpl` - MutatingAdmissionWebhook that intercepts and mutates Jobs, JobSets and Pods.

### Settings

See [values.yaml](./values.yaml)

### See more

Run Kubernetes [Jobs](./jobs.md) and [JobSets](./jobsets.md).
