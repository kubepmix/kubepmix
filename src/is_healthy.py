#!/usr/bin/env python3
import sys
import urllib.request

from config import KUBE_PMIX_HEALTHCHECK_PORT

try:
    urllib.request.urlopen(f"http://localhost:{KUBE_PMIX_HEALTHCHECK_PORT}/healthz", timeout=1)
except Exception:
    sys.exit(1)
