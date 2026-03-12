# app/cache/simple_cache.py

class SimpleCache:
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ttl=None):
        # TTL ignored for now (intentional)
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)


cache = SimpleCache()
