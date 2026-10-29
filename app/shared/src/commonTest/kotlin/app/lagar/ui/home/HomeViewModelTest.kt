package app.lagar.ui.home

import app.lagar.data.ApiIndex
import app.lagar.data.DocumentResponse
import app.lagar.data.GeoRepository
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
import app.lagar.data.LocalityCount
import app.lagar.data.LocalityIndex
import app.lagar.data.LocalityRepository
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.settings.BookmarkStore
import app.lagar.settings.UserPreferences
import com.russhwolf.settings.MapSettings
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
import kotlin.test.assertNull

@OptIn(ExperimentalCoroutinesApi::class)
class HomeViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private val geo = GeoRepository {
        """
        {"regions": [{"code": "01", "name": "Stockholms län"}, {"code": "14", "name": "Västra Götalands län"}],
         "kommuner": [{"code": "0180", "name": "Stockholm", "regionCode": "01"}, {"code": "1480", "name": "Göteborg", "regionCode": "14"}]}
        """.encodeToByteArray()
    }

    private object NoNational : LagarRepository {
        override suspend fun index(): ApiIndex = error("not read by the Region and Kommun homes")

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage = error("unused")

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    /** Stockholm has one county and two municipal regulations, one of them repealed; every request is recorded. */
    private class Localities : LocalityRepository {
        val requests = mutableListOf<String>()
        private val items = mapOf(
            "region" to mapOf("01" to listOf(item("01fs-2026-3", "county_regulation", null))),
            "municipality" to mapOf(
                "0180" to listOf(item("0180-kfs-2026-12", "municipal_regulation", "2026-09-01"), item("0180-kfs-2013-19", "municipal_regulation", null)),
            ),
        )

        override suspend fun localities(layer: String): LocalityIndex {
            requests += "$layer/index"
            val codes = items.getValue(layer)
            return LocalityIndex(layer, "code", codes.values.sumOf { it.size }, codes.map { (c, v) -> LocalityCount(c, v.size) })
        }

        override suspend fun localityListing(layer: String, code: String, page: Int): ListingPage {
            requests += "$layer/$code/$page"
            val list = items.getValue(layer).getValue(code)
            return ListingPage(layer, null, 1, 1, list.size, list)
        }

        private companion object {
            fun item(id: String, type: String, repealed: String?) = ListingItem(id, id, id, type, null, repealed)
        }
    }

    private fun home(scope: Scope, locality: Locality, localities: Localities = Localities()): HomeData {
        val settings = MapSettings()
        val preferences = UserPreferences(settings).apply { completeOnboarding(scope, locality) }
        val vm = HomeViewModel(NoNational, preferences, BookmarkStore(settings), geo, localities)
        return assertIs<LoadState.Loaded<HomeData>>(vm.state.value).value
    }

    @Test
    fun kommunHomeShowsTheChosenKommunsRegulations() {
        val localities = Localities()
        val data = home(Scope.Kommun, Locality("01", "0180"), localities)
        assertEquals("Stockholm", data.localityName)
        assertEquals("0180", data.localityCode)
        assertEquals(2, data.localityTotal)
        assertEquals(listOf(DisplayLayer.Municipality), data.layers)
        assertEquals(listOf("0180-kfs-2026-12", "0180-kfs-2013-19"), data.recent.map { it.id })
        assertEquals(listOf("0180-kfs-2013-19"), data.inForce.map { it.id })
        assertEquals(listOf("municipality/index", "municipality/0180/1"), localities.requests)
    }

    @Test
    fun regionHomeShowsTheChosenLan() {
        val data = home(Scope.Region, Locality("01", null))
        assertEquals("Stockholms län", data.localityName)
        assertEquals(listOf("01fs-2026-3"), data.inForce.map { it.id })
    }

    @Test
    fun aLocalityWithoutDocumentsIsEmpty() {
        val localities = Localities()
        val data = home(Scope.Kommun, Locality("14", "1480"), localities)
        assertEquals("Göteborg", data.localityName)
        assertEquals(0, data.localityTotal)
        assertEquals(emptyList(), data.layers)
        assertEquals(listOf("municipality/index"), localities.requests)
    }

    @Test
    fun noChosenLocalityMakesNoRequests() {
        val localities = Localities()
        val data = home(Scope.Kommun, Locality("01", null), localities)
        assertNull(data.localityName)
        assertEquals(emptyList(), localities.requests)
    }
}
