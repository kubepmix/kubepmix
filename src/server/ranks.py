import threading

class RankTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._namespaces = {}  # nspace -> {'size': int, 'taken': set}

    def register(self, nspace: str, size: int):
        with self._lock:
            self._namespaces[nspace] = {'size': size, 'taken': set()}

    def assign(self, nspace: str) -> int:
        """Assign the first available rank. Thread-safe."""
        with self._lock:
            ns = self._get(nspace)
            for rank in range(ns['size']):
                if rank not in ns['taken']:
                    ns['taken'].add(rank)
                    return rank
            raise RuntimeError(f"All {ns['size']} ranks already taken in namespace '{nspace}'")

    def claim(self, nspace: str, rank: int) -> int:
        """Claim a specific rank. Raises if already taken or out of range. Thread-safe."""
        with self._lock:
            ns = self._get(nspace)
            if rank < 0 or rank >= ns['size']:
                raise ValueError(f"Rank {rank} out of range for namespace '{nspace}' (size={ns['size']})")
            if rank in ns['taken']:
                raise RuntimeError(f"Rank {rank} already taken in namespace '{nspace}'")
            ns['taken'].add(rank)
            return rank

    def _get(self, nspace: str) -> dict:
        ns = self._namespaces.get(nspace)
        if ns is None:
            raise KeyError(f"Unknown namespace '{nspace}' — was the Job admitted first?")
        return ns
