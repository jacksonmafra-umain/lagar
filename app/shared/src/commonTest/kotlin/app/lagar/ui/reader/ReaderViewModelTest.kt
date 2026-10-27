package app.lagar.ui.reader

import app.lagar.data.ApiIndex
import app.lagar.data.DocumentMeta
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingPage
import app.lagar.domain.LoadState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

@OptIn(ExperimentalCoroutinesApi::class)
class ReaderViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private class FakeRepository(var failing: Boolean) : LagarRepository {
        val requested = mutableListOf<String>()

        override suspend fun document(id: String): DocumentResponse {
            requested += id
            if (failing) throw IllegalStateException("boom")
            return DocumentResponse(
                DocumentMeta(
                    id, "Title", "act", "sfs", "1:1", null, null, null, emptyList(), null, emptyList(),
                    null, null, "sv", false, "https://example.org", "", "",
                ),
                "# Title",
            )
        }

        override suspend fun index(): ApiIndex = error("unused")
        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage = error("unused")
    }

    @Test
    fun loadsTheDocument() {
        val vm = ReaderViewModel(FakeRepository(failing = false), "doc-1")
        val loaded = assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals("# Title", (loaded.value as DocumentResponse).body)
    }

    @Test
    fun failureOffersRetryThatReloads() {
        val repo = FakeRepository(failing = true)
        val vm = ReaderViewModel(repo, "doc-1")
        val failed = assertIs<LoadState.Failed>(vm.state.value)
        repo.failing = false
        failed.retry()
        assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals(listOf("doc-1", "doc-1"), repo.requested)
    }
}
