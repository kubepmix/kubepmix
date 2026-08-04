#!/usr/bin/env python3
import signal
import faulthandler
import asyncio
import logging

from server.kubepmixserver import KubePMIxServer
from server.ranks import RankTracker
from server.webhook import start_webhook
from server.healthcheck import start_healthcheck_server

from config import (
    KUBE_PMIX_NAMESPACE_NAME, KUBE_PMIX_JOB_SIZE,
    KUBE_PMIX_WEBHOOK_ENABLED,
)

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    faulthandler.enable()
    loop = asyncio.get_event_loop()

    pmix_server = KubePMIxServer(loop)
    rank_tracker = RankTracker()

    # If namespace pre-configured in ENV vars - create if before servers starts.
    if KUBE_PMIX_NAMESPACE_NAME:
        print(f"Registering namespace and clients from environment variables: {KUBE_PMIX_NAMESPACE_NAME}, {KUBE_PMIX_JOB_SIZE}")
        pmix_server.register_nspace_and_clients(KUBE_PMIX_NAMESPACE_NAME, KUBE_PMIX_JOB_SIZE)
        rank_tracker.register(KUBE_PMIX_NAMESPACE_NAME, KUBE_PMIX_JOB_SIZE)
    else:
        print("No pre-configured namespace in env vars, skipping creation.")

    webhook_runner = None
    if KUBE_PMIX_WEBHOOK_ENABLED:
        print("Kubernetes admission webhook enabled - starting server...")
        webhook_runner = await start_webhook(pmix_server, rank_tracker)
    else:
        print("Kubernetes admission webhook disabled - not starting server..")

    # Start healthcheck server
    healthcheck_runner = await start_healthcheck_server(pmix_server)

    # Register handler for SIGINT & SIGTERM as stop event
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Stay alive until stop event
    print("KubePMIx: serving...")
    await stop_event.wait()

    print("KubePMIx: shutting down")
    if webhook_runner is not None:
        await webhook_runner.cleanup()
    await healthcheck_runner.cleanup()
    pmix_server.finalize()

if __name__ == "__main__":
    asyncio.run(main())
