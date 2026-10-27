package app.lagar.data

/** Keeps the first successful index for the life of the process; failures are never cached, so retry refetches. */
class CachingRepository(private val delegate: LagarRepository) : LagarRepository by delegate {
    private var cachedIndex: ApiIndex? = null

    override suspend fun index(): ApiIndex = cachedIndex ?: delegate.index().also { cachedIndex = it }
}
