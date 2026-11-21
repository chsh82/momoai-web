"""Process-local listing metadata cache, bound to exact package bytes.

Only ever stores the small derived 'week' label needed for archive listing
rows; never the package itself, never bundle/question/answer content, and
never anything per-user. A cache hit replaces a full unpack_real() (ZIP +
canonical-JSON + static-PDF revalidation of both problem.pdf/answer.pdf) for
bytes already proven valid earlier in this process. Keyed by the exact
sha256 of the package bytes, so a single changed byte is a different key;
revision_id/title/order/visibility are always read fresh from the database
row on every call, never from this cache. A failed validation is never
stored, so a corrupt or tampered package is revalidated (and still
rejected) on every call until replaced with valid bytes. Bounded size with
LRU eviction: an evicted entry is simply cold again (revalidated) the next
time those bytes are listed, not an exactly-once-forever guarantee.
"""
import hashlib
import threading

from .real_source import unpack_real, VERSION
from .versioned_source import PROFILES
from .content_only_r02 import VERSION as CONTENT_ONLY_R02_VERSION

MAX_ENTRIES = 256

_lock = threading.Lock()
_cache = {}
_order = []


def _touch(key):
    try:
        _order.remove(key)
    except ValueError:
        pass
    _order.append(key)


def _evict_if_needed():
    while len(_order) > MAX_ENTRIES:
        oldest = _order.pop(0)
        _cache.pop(oldest, None)


def _week_from_manifest_and_source(manifest, source):
    version = manifest['source_version']
    if version == 'accepted-real-bank-v1':
        return source['acceptance']['issue']
    if version == CONTENT_ONLY_R02_VERSION:
        return 'W3'
    if version == VERSION:
        return 'W1'
    return 'W' + str(PROFILES[version]['week'])


def week_for_package(package_bytes):
    """Return the archive-listing 'week' label for these exact package bytes.

    Performs the real unpack_real() validation (ZIP/canonical-JSON/
    static-PDF checks on both PDFs) exactly once per distinct byte sequence
    ever seen successfully in this process, then reuses that result for
    every later (or concurrently blocked) caller with the same bytes. The
    lock is held for the full validate-then-populate critical section, so
    concurrent callers for the SAME bytes serialize behind the first one
    and then observe a cache hit, instead of each re-validating; a failed
    validation is never cached, so it is retried (and still rejected) on
    every subsequent call until the bytes change.
    """
    key = hashlib.sha256(package_bytes).hexdigest()
    with _lock:
        if key in _cache:
            _touch(key)
            return _cache[key]
        _, _, manifest, source = unpack_real(package_bytes)
        week = _week_from_manifest_and_source(manifest, source)
        _cache[key] = week
        _touch(key)
        _evict_if_needed()
        return week


def cache_size():
    with _lock:
        return len(_cache)


def clear():
    with _lock:
        _cache.clear()
        _order.clear()
