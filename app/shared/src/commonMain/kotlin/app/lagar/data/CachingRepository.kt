package app.lagar.data

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Keeps the first successful index for the life of the process. Concurrent callers share one fetch: the
 * rest wait on the lock and then read the cache. Failures are never cached, so the next caller refetches,
 * and a cancelled caller only leaves the queue; it cannot fail the others.
 */
class CachingRepository(private val delegate: LagarRepository) : LagarRepository by delegate {
    private val lock = Mutex()
    private var cachedIndex: ApiIndex? = null

    override suspend fun index(): ApiIndex = lock.withLock {
        cachedIndex ?: delegate.index().also { cachedIndex = it }
    }
}
