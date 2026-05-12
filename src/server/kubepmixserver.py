import asyncio
import pmix
from concurrent.futures import ThreadPoolExecutor

from typing import Any

from server.dmodex_parser import get_btl_endpoints

class KubePMIxServer(pmix.PMIxServer):
    def __init__(self, port, iface, event_loop):
        print(f"[ Kube PMIx Server ] Running PMIx server init with port={port}, iface={iface}")

        super().__init__()
        self._event_loop = event_loop

        # Executor for printing dmodex data when ready
        self._dmodex_executor = ThreadPoolExecutor(max_workers=1)

        rc = self.init([
            {'key': 'pmix.srv.nspace', 'value': 'kubepmix', 'val_type': pmix.PMIX_STRING},
            {'key': 'pmix.tcp.ipv4', 'value': port, 'val_type': pmix.PMIX_INT},
            {'key': 'pmix.tcp.ifinclude', 'value': iface,  'val_type': pmix.PMIX_STRING},
            {'key': 'pmix.tcp.disipv6', 'value': True,  'val_type': pmix.PMIX_BOOL},
            {'key': 'pmix.iof.local', 'value': False, 'val_type': pmix.PMIX_BOOL},
            {'key': 'pmix.tcp.repuri',  'value': '-',   'val_type': pmix.PMIX_STRING},  # print URI to stdout
        ], self._callbacks())

        if rc != pmix.PMIX_SUCCESS:
            raise RuntimeError(f"PMIxServer initialization failed with code: {rc}")

        self._register_for_events()
        print(f"[ Kube PMIx Server ] Initialized. Version: {self.get_version()}")

        self._namespaces = {}  # Track namespaces and client counts for cleanup

    @staticmethod
    def _normalize_proc(proc):
        if isinstance(proc, dict):
            return {'nspace': proc.get('nspace'), 'rank': proc.get('rank')}
        if isinstance(proc, tuple) and len(proc) >= 2:
            return {'nspace': proc[0], 'rank': proc[1]}

        nspace = getattr(proc, 'nspace', None)
        rank = getattr(proc, 'rank', None)
        if nspace is not None and rank is not None:
            return {'nspace': nspace, 'rank': rank}

        return proc

    @staticmethod
    def _proc_label(proc):
        if isinstance(proc, dict):
            return f"[ {proc.get('nspace')} | {proc.get('rank')} ]"
        return f"[ {proc} ]"

    def _register_for_events(self):  
        """Register the server to receive events"""  

        def event_handler(evid: int, st: int, pysource: dict, pyinfo: list, pyresults: list):  
            proc_label = f"[ {pysource.get('nspace')} | {pysource.get('rank')} ]"  
            print(f"{proc_label} Event: Received {evid} with status {st} ({self.error_string(st)})") 
            if st == pmix.PMIX_ERR_LOST_CONNECTION: 
                self._namespaces[pysource['nspace']]['abortedClients'] += 1
                print(f"{proc_label} Detected lost connection event. Namespace status: {self._namespaces[pysource['nspace']]}")
                self._cleanup_if_all_finalized(pysource['nspace'])
            return pmix.PMIX_EVENT_ACTION_COMPLETE, []

        # Register using the client API - server is also a client of itself! Lol
        codes = [] # Register all codes
        rc, ref = self.register_event_handler(codes, [], event_handler)
        if rc != pmix.PMIX_SUCCESS:
            print(f"Failed to register for connection events: {self.error_string(rc)}")
        else:
            print(f"Successfully registered for connection events with ref {ref}")

    def clientconnected(self, proc: Any, cbfunc: Any, cbdata: dict):
        normalized_proc = self._normalize_proc(proc)  
        self._namespaces[normalized_proc['nspace']]['connectedClients'] += 1
        print(f"{self._proc_label(normalized_proc)} Client connected. Namespace status: {self._namespaces[normalized_proc['nspace']]}")

        if self._event_loop is None:
            raise RuntimeError("Event loop is not started")

        # Schedule to print Modex Data when ready
        self._event_loop.call_soon_threadsafe(self._schedule_dmodex_probe, normalized_proc)

        # Call cbfunc
        self._event_loop.call_soon_threadsafe(cbfunc, pmix.PMIX_SUCCESS, cbdata)
        return pmix.PMIX_SUCCESS

    def clientfinalized(self, proc: Any, cbfunc: Any, cbdata: dict):
        normalized_proc = self._normalize_proc(proc)
        self._namespaces[normalized_proc['nspace']]['disconnectedClients'] += 1
        print(f"{self._proc_label(normalized_proc)} Client finalized. Namespace status: {self._namespaces[normalized_proc['nspace']]}")

        self._cleanup_if_all_finalized(normalized_proc['nspace'])

        if self._event_loop is None:
            raise RuntimeError("Event loop is not started")
        self._event_loop.call_soon_threadsafe(cbfunc, pmix.PMIX_SUCCESS, cbdata)

        return pmix.PMIX_SUCCESS

    # clientaborted is called when client consciously fails and calls PMIx_Abort
    # e.g. when MPI process fails to connect through BTL
    def clientaborted(self, args: dict, cbfunc: Any, cbdata: dict):
        caller = args.get('caller')
        status = args.get('status')
        proc_label = self._proc_label(caller)
        print(f"{proc_label} Client aborted with status {status}. Namespace status: {self._namespaces[caller['nspace']]}")
        self._event_loop.call_soon_threadsafe(cbfunc, pmix.PMIX_SUCCESS, cbdata)
        return pmix.PMIX_SUCCESS

    # Client_register_events is only called by client if codes we register for are "system" - ([-330,-230])
    # Otherwise everything happens inside the process, no server call
    # def client_register_events(self, codes: list, info: list, cbfunc: Any, cbdata: dict)......
    def _callbacks(self):
        return {
            'clientconnected': self.clientconnected,
            'clientfinalized': self.clientfinalized,
            'abort': self.clientaborted,
        }

    async def _run_dmodex_probe(self, proc):
        proc_label = self._proc_label(proc)
        try:
            rc, payload = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(self._dmodex_executor, self.dmodex_request, proc, {}),
                timeout=30.0,
            )

            if rc == pmix.PMIX_SUCCESS:
                data, _length = payload
                endpoints = get_btl_endpoints(data)
                print(f"{proc_label} Registered Modex: {endpoints}")
                return

            print(f"{proc_label} DMODEX request failed, rc={rc}")
        except asyncio.TimeoutError:
            print(f"{proc_label} DMODEX request timed out after 30s")

    def _schedule_dmodex_probe(self, proc):
        task = self._event_loop.create_task(self._run_dmodex_probe(proc))

        def _log_task_result(t):
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                print(f"Unhandled DMODEX probe task error: {exc}")

        task.add_done_callback(_log_task_result)

    def _all_clients_finalized(self, nspace: str) -> bool:
        if nspace not in self._namespaces:
            return False

        if self._namespaces[nspace]['connectedClients'] !=  self._namespaces[nspace]['size']:
            return False

        if self._namespaces[nspace]['connectedClients'] == self._namespaces[nspace]['disconnectedClients'] + self._namespaces[nspace]['abortedClients']:
            return True

    def _cleanup_if_all_finalized(self, nspace: str):
        if not self._all_clients_finalized(nspace):
            return True

        print(f"[ Kube PMIx Server ] Cleaning up namespace '{nspace}' as all clients have finalized or aborted. Namespace status: {self._namespaces[nspace]}")
        if nspace in self._namespaces:
            # del self._namespaces[nspace]
            self.deregister_nspace_and_clients(nspace)
        else:
            print(f"Attempted to clean up non-existent namespace '{nspace}'")

    def register_nspace_and_clients(self, name:str, size:int):
        ranks = [str(i) for i in range(size)]
        (rc, regex) = self.generate_regex(ranks)
        (rc, ppn) = self.generate_ppn(ranks)

        kvals = [{'key':pmix.PMIX_NODE_MAP, 'value':regex, 'val_type':pmix.PMIX_STRING},
                {'key':pmix.PMIX_PROC_MAP, 'value':ppn, 'val_type':pmix.PMIX_STRING},
                {'key':pmix.PMIX_UNIV_SIZE, 'value':size, 'val_type':pmix.PMIX_UINT32},
                {'key':pmix.PMIX_JOB_SIZE, 'value':size, 'val_type':pmix.PMIX_UINT32}]

        print(f"[ Kube PMIx Server ] Registering namespace {name} with PPN: {ppn}, regex: {regex}, job size: {size}")
        rc = self.register_nspace(name, size, kvals)
        print("[ Kube PMIx Server ] Registering clients...")
        for rank in range(size):
            rc = self.register_client({'nspace':name, 'rank':rank}, 0, 0)
            print(f"[ Kube PMIx Server ] Registered client {name}:{rank}, RC: {rc}")

        # Add namespace entry for tracking clients
        nspace_entry = {
            'name': name,
            'size': size,
            'connectedClients': 0,
            'disconnectedClients': 0,
            'abortedClients': 0
        }

        self._namespaces[name] = nspace_entry

    def deregister_nspace_and_clients(self, name:str):
        print(f"[ Kube PMIx Server ] To be implemented: Cleanup of the namespace {name}...")
        return True
