import logging

from aiohttp import web

from config import KUBE_PMIX_HEALTHCHECK_PORT

log = logging.getLogger(__name__)


async def start_healthcheck_server(pmix_server):
    app = web.Application()
    app['pmix'] = pmix_server
    app.router.add_get('/healthz', healthz)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', KUBE_PMIX_HEALTHCHECK_PORT)
    await site.start()
    log.info("Healthcheck listening on :%d", KUBE_PMIX_HEALTHCHECK_PORT)
    return runner


async def healthz(request):
    if request.app['pmix'].initialized():
        return web.Response(text="ok")
    return web.Response(status=503, text="not ready")
