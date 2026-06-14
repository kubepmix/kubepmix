apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "kubepmix.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    app.kubernetes.io/name: {{ include "kubepmix.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
    helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "kubepmix.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    app.kubernetes.io/name: {{ include "kubepmix.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
    helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "kubepmix.name" . }}
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "kubepmix.name" . }}
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      serviceAccountName: {{ include "kubepmix.fullname" . }}
      containers:
        - name: {{ include "kubepmix.name" . }}
          image: {{ .Values.server.image }}
          ports:
            - name: pmix
              containerPort: {{ .Values.server.pmix.port }}
              protocol: TCP
            - name: webhook
              containerPort: {{ .Values.server.webhook.port }}
              protocol: TCP
          env:
            {{- range .Values.server.pmix.envs }}
            - name: {{ .name }}
              value: {{ .value | quote }}
            {{- end }}
            - name: PMIX_MCA_ptl_tcp_ipv4_port
              value: {{ .Values.server.pmix.port | quote }}
            - name: PMIX_MCA_psec
              value: "none" # Do not check processes UID and GUID
            - name: KUBE_PMIX_WEBHOOK_ENABLED
              value: "true"
            - name: KUBE_PMIX_WEBHOOK_PORT
              value: {{ .Values.server.webhook.port | quote }}
            - name: KUBE_PMIX_TLS_CERT
              value: /tls/tls.crt
            - name: KUBE_PMIX_TLS_KEY
              value: /tls/tls.key
          volumeMounts:
            - name: tls
              mountPath: /tls
              readOnly: true
      volumes:
        - name: tls
          secret:
            secretName: {{ printf "%s-tls" (include "kubepmix.fullname" .) | quote }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "kubepmix.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    app.kubernetes.io/name: {{ include "kubepmix.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
    helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
spec:
  selector:
    app.kubernetes.io/name: {{ include "kubepmix.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
  ports:
    - name: pmix
      port: {{ .Values.server.pmix.port }}
      targetPort: pmix
      protocol: TCP
    - name: webhook
      port: 443
      targetPort: webhook
      protocol: TCP
