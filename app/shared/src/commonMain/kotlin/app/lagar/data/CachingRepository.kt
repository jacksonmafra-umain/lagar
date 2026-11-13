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

/**
 * Keeps the service catalogue and the by-norm index for the life of the process, each fetched at most once on
 * success, with the same locking as [CachingRepository]. A file the API answers 404 for is cached as empty;
 * other failures are not cached. [servicesForNorm] reads the catalogue only when the index lists the norm.
 */
class CachingServiceRepository(private val source: ServiceSource) : ServiceRepository {
    private val catalogLock = Mutex()
    private var catalog: ServiceCatalog? = null
    private val indexLock = Mutex()
    private var normIndex: ServiceNormIndex? = null

    override suspend fun serviceCatalog(): ServiceCatalog = catalogLock.withLock {
        catalog ?: emptyWhenMissing(ServiceCatalog.Empty) { source.serviceCatalog() }.also { catalog = it }
    }

    override suspend fun servicesForNorm(id: String): List<ServiceSummary> {
        val ids = normIndex().serviceIds(id)
        if (ids.isEmpty()) return emptyList()
        val services = serviceCatalog().services.associateBy { it.id }
        return ids.mapNotNull { services[it] }
    }

    private suspend fun normIndex(): ServiceNormIndex = indexLock.withLock {
        normIndex ?: emptyWhenMissing(ServiceNormIndex(emptyMap())) { source.serviceNormIndex() }.also { normIndex = it }
    }

    private inline fun <T> emptyWhenMissing(empty: T, fetch: () -> T): T = try {
        fetch()
    } catch (e: ApiException) {
        if (e.notFound) empty else throw e
    }
}
