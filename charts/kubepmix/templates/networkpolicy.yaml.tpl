apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ printf "%s-pmix" (include "kubepmix.fullname" .) | quote }}
  namespace: {{ .Release.Namespace }}
  labels:
    app.kubernetes.io/name: {{ include "kubepmix.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
    helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
spec:
  podSelector:
    matchExpressions:
      - key: {{ ternary "kubepmix.dev/namespace" "kubepmix.dev/networkpolicy-disabled" (eq .Values.scope "Namespace") | quote }}
        operator: Exists
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: {{ ternary "kubepmix.dev/namespace" "kubepmix.dev/networkpolicy-disabled" (eq .Values.scope "Namespace") | quote }}
                operator: Exists
      ports:
        - protocol: TCP
          port: {{ .Values.server.pmix.port }}
