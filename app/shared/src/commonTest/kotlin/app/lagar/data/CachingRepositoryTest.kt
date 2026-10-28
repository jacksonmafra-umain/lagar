package app.lagar.data

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class CachingRepositoryTest {
    private val index = ApiIndex(1, "t", emptyList())

    private class FakeRepository(var result: suspend () -> ApiIndex) : LagarRepository {
        var calls = 0

        override suspend fun index(): ApiIndex {
            calls++
            return result()
        }

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage = error("unused")
        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    @Test
    fun secondCallIsServedFromTheCache() = runTest {
        val delegate = FakeRepository { index }
        val repo = CachingRepository(delegate)
        assertSame(index, repo.index())
        assertSame(index, repo.index())
        assertEquals(1, delegate.calls)
    }

    @Test
    fun failureIsNotCachedAndRetryFetchesAgain() = runTest {
        val delegate = FakeRepository { throw IllegalStateException("boom") }
        val repo = CachingRepository(delegate)
        assertFailsWith<IllegalStateException> { repo.index() }
        delegate.result = { index }
        assertSame(index, repo.index())
        assertEquals(2, delegate.calls)
    }

    @Test
    fun concurrentCallersFetchOnce() = runTest {
        val gate = CompletableDeferred<Unit>()
        val delegate = FakeRepository {
            gate.await()
            index
        }
        val repo = CachingRepository(delegate)
        val callers = List(5) { async { repo.index() } }
        gate.complete(Unit)
        assertEquals(List(5) { index }, callers.awaitAll())
        assertEquals(1, delegate.calls)
    }

    @Test
    fun cancellingTheFetchingCallerDoesNotFailTheOthers() = runTest {
        val gate = CompletableDeferred<Unit>()
        val delegate = FakeRepository {
            gate.await()
            index
        }
        val repo = CachingRepository(delegate)
        val first = async { repo.index() }
        val second = async { repo.index() }
        testScheduler.runCurrent()
        first.cancel()
        gate.complete(Unit)
        assertSame(index, second.await())
    }
}
