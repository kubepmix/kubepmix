---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ printf "%s-controller" (include "kubepmix.fullname" .) | quote }}
  namespace: {{ .Release.Namespace }}
  labels:
    app.kubernetes.io/name: {{ include "kubepmix.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
    helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: {{ include "kubepmix.name" . }}
      app.kubernetes.io/instance: {{ .Release.Name }}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: {{ .Release.Namespace }}
      ports:
        - protocol: TCP
          port: {{ .Values.server.pmix.port }}
    - ports:
        - protocol: TCP
          port: {{ .Values.server.webhook.port }}
