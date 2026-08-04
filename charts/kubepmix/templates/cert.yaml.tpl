apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: {{ printf "%s-selfsigned" (include "kubepmix.fullname" .) | quote }}
  namespace: {{ .Release.Namespace }}
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: {{ printf "%s-tls" (include "kubepmix.fullname" .) | quote }}
  namespace: {{ .Release.Namespace }}
spec:
  secretName: {{ printf "%s-tls" (include "kubepmix.fullname" .) | quote }}
  issuerRef:
    name: {{ printf "%s-selfsigned" (include "kubepmix.fullname" .) | quote }}
    kind: Issuer
  dnsNames:
    - {{ include "kubepmix.fullname" . | quote }}
    - {{ printf "%s.%s.svc" (include "kubepmix.fullname" .) .Release.Namespace | quote }}
    - {{ printf "%s.%s.svc.cluster.local" (include "kubepmix.fullname" .) .Release.Namespace | quote }}
