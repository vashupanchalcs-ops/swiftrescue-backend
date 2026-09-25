"""Short-lived read cache for hospital capacity and dashboards.

PostgreSQL remains the source of truth. Cache failures are deliberately
fail-open because dispatch must continue if Redis is temporarily unavailable.
"""

from django.core.cache import cache


HOSPITAL_CACHE_TTL = 20


def dashboard_key(hospital_id):
    return f"hospital-dashboard:{hospital_id}"


def list_key(query_string):
    return f"hospital-list:{query_string or 'all'}"


def invalidate_hospital_cache(hospital_id=None):
    keys = []
    if hospital_id is not None:
        keys.append(dashboard_key(hospital_id))
    if keys:
        try:
            cache.delete_many(keys)
        except Exception:
            pass
    # List keys include filters and are intentionally short lived.  There is
    # no portable wildcard delete across Django cache backends.


def cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        return None


def cache_set(key, value, timeout=HOSPITAL_CACHE_TTL):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        pass
