#!/usr/bin/env python3
import signal
import faulthandler
import asyncio

from server.kubepmixserver import KubePMIxServer
from server.ranks import RankTracker
from server.webhook import start_webhook

from config import (
    KUBE_PMIX_SERVER_PORT, KUBE_PMIX_SERVER_IFACE,
    KUBE_PMIX_NAMESPACE_NAME, KUBE_PMIX_JOB_SIZE,
    KUBE_PMIX_WEBHOOK_ENABLED,
)

async def main():
    faulthandler.enable()
    loop = asyncio.get_event_loop()

    pmix_server = KubePMIxServer(KUBE_PMIX_SERVER_PORT, KUBE_PMIX_SERVER_IFACE, loop)
    rank_tracker = RankTracker()

    # If namespace pre-configured in ENV vars - create if before servers starts.
    if KUBE_PMIX_NAMESPACE_NAME:
        pmix_server.register_nspace_and_clients(KUBE_PMIX_NAMESPACE_NAME, KUBE_PMIX_JOB_SIZE)
        rank_tracker.register(KUBE_PMIX_NAMESPACE_NAME, KUBE_PMIX_JOB_SIZE)

    if KUBE_PMIX_WEBHOOK_ENABLED:
        start_webhook(pmix_server, rank_tracker, loop)

    # Register handler for SIGINT & SIGTERM as stop event
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Stay alive until stop event
    print("KubePMIx: serving...")
    await stop_event.wait()

    print("KubePMIx: shutting down")
    pmix_server.finalize()

if __name__ == "__main__":
    asyncio.run(main())
