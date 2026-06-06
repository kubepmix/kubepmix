apiVersion: admissionregistration.k8s.io/v1
kind: MutatingWebhookConfiguration
metadata:
  name: {{ include "kubepmix.fullname" . }}
  annotations:
    cert-manager.io/inject-ca-from: {{ printf "%s/%s-tls" .Release.Namespace (include "kubepmix.fullname" .) | quote }}
webhooks:
  - name: jobs.kube-pmix.io
    admissionReviewVersions: ["v1"]
    sideEffects: None
    failurePolicy: Ignore
    clientConfig:
      service:
        name: {{ include "kubepmix.fullname" . }}
        namespace: {{ .Release.Namespace }}
        path: /mutate/jobs
        port: 443
    objectSelector:
      matchLabels:
        kubepmix.dev/enabled: "true"
    rules:
      - apiGroups: ["batch"]
        apiVersions: ["v1"]
        resources: ["jobs"]
        operations: ["CREATE"]
        scope: "*"
{{- if eq .Values.scope "Namespace" }}
    namespaceSelector:
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: In
          values: [{{ .Release.Namespace | quote }}]
{{- end }}

  - name: pods.kube-pmix.io
    admissionReviewVersions: ["v1"]
    sideEffects: None
    failurePolicy: Fail
    clientConfig:
      service:
        name: {{ include "kubepmix.fullname" . }}
        namespace: {{ .Release.Namespace }}
        path: /mutate/pods
        port: 443
    objectSelector:
      matchExpressions:
        - key: kubepmix.dev/namespace
          operator: Exists
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        resources: ["pods"]
        operations: ["CREATE"]
        scope: "*"
{{- if eq .Values.scope "Namespace" }}
    namespaceSelector:
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: In
          values: [{{ .Release.Namespace | quote }}]
{{- end }}
