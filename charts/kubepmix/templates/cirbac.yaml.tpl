apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ include "kubepmix.fullname" . }}-ci-role
  namespace: {{ .Release.Namespace }}
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["serviceaccounts", "services", "configmaps"]
    verbs: ["get", "create", "delete", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "create", "delete"]
  - apiGroups: ["apps"]
    resources: ["replicasets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["get", "create", "delete", "list"]
  - apiGroups: ["jobset.x-k8s.io"]
    resources: ["jobsets"]
    verbs: ["get", "create", "delete", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ include "kubepmix.fullname" . }}-ci-role
  namespace: {{ .Release.Namespace }}
subjects:
  # Hardcoded this
  - kind: ServiceAccount 
    name: kubepmix-selfhosted-test-gha-rs-no-permission
    namespace: arc
roleRef:
  kind: Role
  name: {{ include "kubepmix.fullname" . }}-ci-role
  apiGroup: rbac.authorization.k8s.io
