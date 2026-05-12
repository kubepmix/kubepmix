import os
KUBE_PMIX_SERVER_PORT  = int(os.getenv('KUBE_PMIX_SERVER_PORT', '3333'))
KUBE_PMIX_SERVER_IFACE = os.getenv('KUBE_PMIX_SERVER_IFACE', 'eth0')

# Set both to enable static namespace registration on startup.
KUBE_PMIX_NAMESPACE_NAME = os.getenv('KUBE_PMIX_NAMESPACE_NAME')
KUBE_PMIX_JOB_SIZE       = int(os.getenv('KUBE_PMIX_JOB_SIZE', '0'))

# Set to 'true' to enable the admission webhook.
KUBE_PMIX_WEBHOOK_ENABLED = os.getenv('KUBE_PMIX_WEBHOOK_ENABLED', 'false').lower() == 'true'
KUBE_PMIX_WEBHOOK_PORT    = int(os.getenv('KUBE_PMIX_WEBHOOK_PORT', '8443'))
KUBE_PMIX_TLS_CERT        = os.getenv('KUBE_PMIX_TLS_CERT', '/tls/tls.crt')
KUBE_PMIX_TLS_KEY         = os.getenv('KUBE_PMIX_TLS_KEY',  '/tls/tls.key')
