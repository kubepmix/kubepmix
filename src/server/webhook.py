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

    is_jobset = 'jobset.sigs.k8s.io/jobset-uid' in labels

    if is_jobset:
        jobset_uid = labels['jobset.sigs.k8s.io/jobset-uid']
        jobset_name = labels.get('jobset.sigs.k8s.io/jobset-name', 'unknown-jobset')
        restart_attempt = labels.get('jobset.sigs.k8s.io/restart-attempt', '0')
        nspace = f"pmix-{jobset_name}-{jobset_uid}-{restart_attempt}"
        log.info(f"Job is part of JobSet: using nspace={nspace}")
    else:
        nspace = f"pmix-{job['metadata']['name']}-{uuid.uuid4().hex[:8]}"
        log.info(f"Job is not part of JobSet: using nspace={nspace}")

    nspaces_to_create = [(nspace, None)]

    init_container_depth = labels.get('kubepmix.dev/initContainerDepth', None)

    if is_jobset and init_container_depth is not None:
        init_container_world_size = int(labels.get('kubepmix.dev/initContainerWorldSize', labels.get('kubepmix.dev/size', '0')))
        nspaces_to_create.extend([
            (f"{nspace}-init-{i}", init_container_world_size)
            for i in range(int(init_container_depth) + 1)
        ])
        log.info(
            "Job has init containers, considering namespaces list: %s",
            [ns for ns, _ in nspaces_to_create],
        )

    # Check if we have set kubepmix.dev/create to true. If so - register the namespace. Always create for standalone job.
    if labels.get('kubepmix.dev/create') == 'true' or not is_jobset:

        # For JobSets - create with size specified in kubepmix.dev/size
        if is_jobset:
            parallelism = int(labels.get('kubepmix.dev/size', '0'))
            log.info(f"Create mode: Registering namespace {nspace} with size: {parallelism} (from kubepmix.dev/size)")
        # For standalone Jobs - create with size specified in job spec parallelism
        else:
            parallelism = job['spec'].get('parallelism', 0)
            log.info(f"Create mode: Registering namespace {nspace} with size: {parallelism} (from job spec)")

        for ns, ns_size in nspaces_to_create:
            size = parallelism if ns_size is None else ns_size
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    request.app['pmix'].register_nspace_and_clients,
                    ns, size,
                )
            except Exception as e:
                log.error("PMIx registration failed for %s: %s", ns, e)
                patch = _annotation_patch(job, 'kubepmix.dev/registration-warning', str(e))
                return _allow(uid, patch)

            request.app['ranks'].register(ns, size)

    log.info(f"Allowing job with nspaces={[ns for ns, _ in nspaces_to_create]}, will just mutate the pod labels")
    return _allow(uid, _label_patch(job, nspace, init_container_depth))

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

    init_container_depth = labels.get('kubepmix.dev/initContainerDepth')
    init_depth = None
    if init_container_depth is not None:
        try:
            init_depth = int(init_container_depth)
            if init_depth < 0:
                raise ValueError("initContainerDepth must be >= 0")
        except ValueError as e:
            log.error("Invalid kubepmix.dev/initContainerDepth=%r: %s", init_container_depth, e)
            return _deny(uid, f"Invalid kubepmix.dev/initContainerDepth: {init_container_depth}")

    log.info("Pod intercepted: %s/%s nspace=%s",
             pod['metadata'].get('namespace', ''), pod['metadata'].get('name', '<pending>'), nspace)

    container_ranks = labels.get('kubepmix.dev/containerRanks')
    container_rank_values = None
    if container_ranks is not None:
        try:
            container_rank_values = [int(x.strip()) for x in container_ranks.split('-') if x.strip() != '']
        except ValueError as e:
            log.error("Invalid kubepmix.dev/containerRanks=%r: %s", container_ranks, e)
            return _deny(uid, f"Invalid kubepmix.dev/containerRanks: {container_ranks}")

    rank_label = labels.get('kubepmix.dev/rank')
    patch = []

    # Mutate normal containers with the main namespace.
    containers = pod.get('spec', {}).get('containers', [])
    try:
        if container_rank_values is not None:
            for idx, explicit_rank in enumerate(container_rank_values[:len(containers)]):
                rank = request.app['ranks'].claim(nspace, explicit_rank)

                env = {}
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda r=rank, e=env: request.app['pmix'].setup_fork({'nspace': nspace, 'rank': r}, e),
                )

                env['PMIX_SECURITY_MODE'] = 'none'
                env['PMIX_GDS_MODULE'] = 'hash'
                patch.extend(_env_patch(pod, env, container_key='containers', container_index=idx))
        else:
            if rank_label is not None:
                rank = request.app['ranks'].claim(nspace, int(rank_label))
            else:
                rank = request.app['ranks'].assign(nspace)

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
            patch.extend(_env_patch(pod, env, container_key='containers'))
    except (KeyError, ValueError, RuntimeError) as e:
        log.error("Rank assignment failed for %s: %s", nspace, e)
        return _deny(uid, str(e))

    # If requested, mutate initContainers[0..depth] using namespace-init-{index}.
    if init_depth is not None:
        init_containers = pod.get('spec', {}).get('initContainers', [])
        for init_idx in range(init_depth + 1):
            if init_idx >= len(init_containers):
                log.warning(
                    "initContainerDepth requested index %d but pod has %d initContainers; skipping",
                    init_idx, len(init_containers)
                )
                continue

            init_nspace = f"{nspace}-init-{init_idx}"
            try:
                init_rank = request.app['ranks'].assign(init_nspace)
            except (KeyError, ValueError, RuntimeError) as e:
                log.error("Rank assignment failed for %s: %s", init_nspace, e)
                return _deny(uid, str(e))

            init_env = {}
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda n=init_nspace, r=init_rank, e=init_env: request.app['pmix'].setup_fork({'nspace': n, 'rank': r}, e),
                )
            except Exception as e:
                log.error("setup_fork failed for %s:%d: %s", init_nspace, init_rank, e)
                return _deny(uid, f"PMIx setup_fork failed: {e}")

            init_env['PMIX_SECURITY_MODE'] = 'none'
            init_env['PMIX_GDS_MODULE'] = 'hash'
            patch.extend(_env_patch(
                pod,
                init_env,
                container_key='initContainers',
                container_index=init_idx,
            ))

    return _allow(uid, patch)


# --- Patch helpers ---

def _label_patch(job, nspace, init_container_depth=None):
    tmpl_meta = job['spec']['template'].get('metadata')
    if tmpl_meta is None:
        labels = {"kubepmix.dev/namespace": nspace}
        if init_container_depth is not None:
            labels["kubepmix.dev/initContainerDepth"] = init_container_depth
        return [{"op": "add", "path": "/spec/template/metadata",
                 "value": {"labels": labels}}]
    if tmpl_meta.get('labels') is None:
        labels = {"kubepmix.dev/namespace": nspace}
        if init_container_depth is not None:
            labels["kubepmix.dev/initContainerDepth"] = init_container_depth
        return [{"op": "add", "path": "/spec/template/metadata/labels",
                 "value": labels}]
    patch = [{"op": "add", "path": "/spec/template/metadata/labels/kubepmix.dev~1namespace",
             "value": nspace}]
    if init_container_depth is not None:
        patch.append({"op": "add", "path": "/spec/template/metadata/labels/kubepmix.dev~1initContainerDepth",
                      "value": init_container_depth})
    return patch

def _env_patch(pod, env, container_key='containers', container_index=None):
    patch = []
    env_list = [{"name": k, "value": v} for k, v in env.items()]
    containers = pod.get('spec', {}).get(container_key, [])
    if container_index is not None:
        if container_index < 0 or container_index >= len(containers):
            return patch
        index_iter = [container_index]
    else:
        index_iter = range(len(containers))

    for i in index_iter:
        container = containers[i]
        if container.get('env') is None:
            patch.append({"op": "add", "path": f"/spec/{container_key}/{i}/env", "value": env_list})
        else:
            for ev in env_list:
                patch.append({"op": "add", "path": f"/spec/{container_key}/{i}/env/-", "value": ev})
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
