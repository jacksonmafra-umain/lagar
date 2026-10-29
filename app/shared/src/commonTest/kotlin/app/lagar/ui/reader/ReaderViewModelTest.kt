package app.lagar.ui.reader

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.Catalog
import app.lagar.data.DocumentMeta
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
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

    private class FakeRepository(var failing: Boolean, val listed: List<String> = emptyList()) : LagarRepository {
        val requested = mutableListOf<String>()
        var listings = 0

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

        override suspend fun index(): ApiIndex = ApiIndex(1, "t", listOf(ApiLayer("sfs", listed.size, listOf(ApiSeries("act", listed.size)))))

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            listings++
            if (failing) throw IllegalStateException("boom")
            val items = listed.map { ListingItem(it, "Title", "1:1", "act", null, null) }
            return ListingPage(layer, type, 1, 1, items.size, items)
        }
    }

    private fun viewModel(repo: FakeRepository, id: String = "doc-1") = ReaderViewModel(repo, Catalog(repo), id)

    @Test
    fun loadsTheDocument() {
        val vm = viewModel(FakeRepository(failing = false))
        val loaded = assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals("# Title", (loaded.value as DocumentResponse).body)
    }

    @Test
    fun failureOffersRetryThatReloads() {
        val repo = FakeRepository(failing = true)
        val vm = viewModel(repo)
        val failed = assertIs<LoadState.Failed>(vm.state.value)
        repo.failing = false
        failed.retry()
        assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals(listOf("doc-1", "doc-1"), repo.requested)
    }

    @Test
    fun linksOnlyTheAmendmentsTheApiPublishes() {
        val repo = FakeRepository(failing = false, listed = listOf("sfs-1983-240", "sfs-1962-700", "sfs-n2019-2"))
        val vm = viewModel(repo, id = "sfs-1962-700")
        vm.resolveAmendmentLinks(listOf("1970:225", "1983:240", "1962:700", "N2019:2", "not a number"))
        assertEquals(mapOf("1983:240" to "sfs-1983-240", "N2019:2" to "sfs-n2019-2"), vm.linkedAmendments.value)
        vm.resolveAmendmentLinks(listOf("1983:240"))
        assertEquals(1, repo.listings)
    }

    @Test
    fun aFailedLookupLeavesPlainNumbersAndCanRetry() {
        val repo = FakeRepository(failing = false, listed = listOf("sfs-1983-240"))
        val vm = viewModel(repo)
        repo.failing = true
        vm.resolveAmendmentLinks(listOf("1983:240"))
        assertEquals(emptyMap(), vm.linkedAmendments.value)
        repo.failing = false
        vm.resolveAmendmentLinks(listOf("1983:240"))
        assertEquals(mapOf("1983:240" to "sfs-1983-240"), vm.linkedAmendments.value)
    }
}
