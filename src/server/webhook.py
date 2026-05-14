import asyncio
import base64
import json
import logging
import ssl
import uuid

from aiohttp import web

from config import KUBE_PMIX_WEBHOOK_PORT, KUBE_PMIX_TLS_CERT, KUBE_PMIX_TLS_KEY

log = logging.getLogger(__name__)


async def start_webhook(pmix_server, rank_tracker):
    app = web.Application()
    app['pmix'] = pmix_server
    app['ranks'] = rank_tracker
    app.router.add_post('/mutate/jobs', mutate_job)
    app.router.add_post('/mutate/pods', mutate_pod)

    runner = web.AppRunner(app)
    await runner.setup()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(KUBE_PMIX_TLS_CERT, KUBE_PMIX_TLS_KEY)
    site = web.TCPSite(runner, '0.0.0.0', KUBE_PMIX_WEBHOOK_PORT, ssl_context=ctx)
    await site.start()
    log.info("Webhook listening on :%d", KUBE_PMIX_WEBHOOK_PORT)
    return runner


# --- Job webhook ---

async def mutate_job(request):
    body = await request.json()
    review = body['request']
    uid = review['uid']
    job = review['object']

    labels = job.get('metadata', {}).get('labels', {})
    if labels.get('kubepmix.dev/enabled') != 'true':
        return _allow(uid)

    log.info("Job intercepted")


    # Check if we are owned by job-set. If we have label: jobset.sigs.k8s.io/jobset-uid
    # If so, set our ns_base_name to "{jobset.sigs.k8s.io/jobset-name}-{jobset.sigs.k8s.io/jobset-uid}-{jobset.sigs.k8s.io/restart-attempt}" instead of "pmix-{job-name}"

    if 'jobset.sigs.k8s.io/jobset-uid' in labels:
        jobset_uid = labels['jobset.sigs.k8s.io/jobset-uid']
        jobset_name = labels.get('jobset.sigs.k8s.io/jobset-name', 'unknown-jobset')
        restart_attempt = labels.get('jobset.sigs.k8s.io/restart-attempt', '0')
        parallelism = labels.get('kubepmix/restart-attempt', '0')

        nspace = f"pmix-{jobset_name}-{jobset_uid}-{restart_attempt}"

        log.info(f"Job is part of JobSet: using nspace={nspace}")
    else:
        nspace = f"pmix-{job['metadata']['name']}-{uuid.uuid4().hex[:8]}"

        log.info(f"Job is not part of JobSet: using nspace={nspace}")


    # Check if we have set kubepmix.dev/create to true. If so - register the namespace. Always create for standalone job.
    if labels.get('kubepmix.dev/create') == 'true' or 'jobset.sigs.k8s.io/jobset-uid' not in labels:
        
        # For JobSets - create with size specified in kubepmix.dev/size
        if 'jobset.sigs.k8s.io/jobset-uid' in labels:
            parallelism=int(labels.get('kubepmix.dev/size', '0'))
            log.info(f"Create mode: Registering namespace {nspace} with size: {parallelism} (from kubepmix.dev/size)")
        # For standalone Jobs - create with size specified in job spec parallelism
        else:
            parallelism=job['spec'].get('parallelism', 0)
            log.info(f"Create mode: Registering namespace {nspace} with size: {parallelism} (from job spec)")
            
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                request.app['pmix'].register_nspace_and_clients,
                nspace, parallelism,
            )
        except Exception as e:
            log.error("PMIx registration failed for %s: %s", nspace, e)
            patch = _annotation_patch(job, 'kubepmix.dev/registration-warning', str(e))
            return _allow(uid, patch)
        
        request.app['ranks'].register(nspace, parallelism)

    log.info(f"Allowing job with nspace={nspace} parallelism={parallelism}, will just mutate the pod labels")
    return _allow(uid, _label_patch(job, nspace))

# --- Pod webhook ---

async def mutate_pod(request):
    body = await request.json()
    review = body['request']
    uid = review['uid']
    pod = review['object']

    labels = pod.get('metadata', {}).get('labels', {})
    nspace = labels.get('kubepmix.dev/namespace')
    if not nspace:
        return _allow(uid)

    log.info("Pod intercepted: %s/%s nspace=%s",
             pod['metadata'].get('namespace', ''), pod['metadata'].get('name', '<pending>'), nspace)

    rank_label = labels.get('kubepmix.dev/rank')
    try:
        if rank_label is not None:
            rank = request.app['ranks'].claim(nspace, int(rank_label))
        else:
            rank = request.app['ranks'].assign(nspace)
    except (KeyError, ValueError, RuntimeError) as e:
        log.error("Rank assignment failed: %s", e)
        return _deny(uid, str(e))

    log.info("Assigned rank %d to pod %s nspace=%s (explicit=%s)",
             rank, pod['metadata'].get('name', '<pending>'), nspace, rank_label is not None)

    env = {}
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: request.app['pmix'].setup_fork({'nspace': nspace, 'rank': rank}, env),
        )
    except Exception as e:
        log.error("setup_fork failed for %s:%d: %s", nspace, rank, e)
        return _deny(uid, f"PMIx setup_fork failed: {e}")

    env['PMIX_SECURITY_MODE'] = 'none'
    env['PMIX_GDS_MODULE'] = 'hash'
    return _allow(uid, _env_patch(pod, env))


# --- Patch helpers ---

def _label_patch(job, nspace):
    tmpl_meta = job['spec']['template'].get('metadata')
    if tmpl_meta is None:
        return [{"op": "add", "path": "/spec/template/metadata",
                 "value": {"labels": {"kubepmix.dev/namespace": nspace}}}]
    if tmpl_meta.get('labels') is None:
        return [{"op": "add", "path": "/spec/template/metadata/labels",
                 "value": {"kubepmix.dev/namespace": nspace}}]
    return [{"op": "add", "path": "/spec/template/metadata/labels/kubepmix.dev~1namespace",
             "value": nspace}]


def _env_patch(pod, env):
    patch = []
    env_list = [{"name": k, "value": v} for k, v in env.items()]
    for i, container in enumerate(pod.get('spec', {}).get('containers', [])):
        if container.get('env') is None:
            patch.append({"op": "add", "path": f"/spec/containers/{i}/env", "value": env_list})
        else:
            for ev in env_list:
                patch.append({"op": "add", "path": f"/spec/containers/{i}/env/-", "value": ev})
    return patch


def _annotation_patch(job, key, value):
    escaped = key.replace('~', '~0').replace('/', '~1')
    if job.get('metadata', {}).get('annotations') is None:
        return [{"op": "add", "path": "/metadata/annotations", "value": {key: value}}]
    return [{"op": "add", "path": f"/metadata/annotations/{escaped}", "value": value}]


# --- Response helpers ---
def _allow(uid, patch=None):
    response = {"uid": uid, "allowed": True}
    if patch:
        response["patch"] = base64.b64encode(json.dumps(patch).encode()).decode()
        response["patchType"] = "JSONPatch"
    return web.json_response({
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": response,
    })

def _deny(uid, message):
    return web.json_response({
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {"uid": uid, "allowed": False, "status": {"message": message}},
    })
