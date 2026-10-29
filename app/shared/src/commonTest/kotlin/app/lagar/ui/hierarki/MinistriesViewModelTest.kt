package app.lagar.ui.hierarki

import app.lagar.data.ApiMinistry
import app.lagar.data.ListingPage
import app.lagar.data.MinistryIndex
import app.lagar.data.MinistryRepository
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
class MinistriesViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private class FakeMinistries : MinistryRepository {
        var fail = false
        val requests = mutableListOf<String>()

        override suspend fun ministries(layer: String, type: String): MinistryIndex {
            requests += "$layer/$type"
            if (fail) throw IllegalStateException("offline")
            return MinistryIndex(
                layer, type, total = 5, unassigned = 1,
                ministries = listOf(ApiMinistry("finansdepartementet", "Finansdepartementet", 3), ApiMinistry("riksbanken", "Riksbanken", 1)),
            )
        }

        override suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int): ListingPage = error("unused")
    }

    @Test
    fun loadsTheSeriesIndex() {
        val repo = FakeMinistries()
        val vm = MinistriesViewModel(repo, "sfs", "ordinance")
        val loaded = assertIs<LoadState.Loaded<MinistryIndex>>(vm.state.value)
        assertEquals(listOf("finansdepartementet", "riksbanken"), loaded.value.ministries.map { it.id })
        assertEquals(1, loaded.value.unassigned)
        assertEquals(listOf("sfs/ordinance"), repo.requests)
    }

    @Test
    fun failureRetries() {
        val repo = FakeMinistries().apply { fail = true }
        val vm = MinistriesViewModel(repo, "sfs", "act")
        val failed = assertIs<LoadState.Failed>(vm.state.value)
        repo.fail = false
        failed.retry()
        assertIs<LoadState.Loaded<MinistryIndex>>(vm.state.value)
        assertEquals(listOf("sfs/act", "sfs/act"), repo.requests)
    }
}
