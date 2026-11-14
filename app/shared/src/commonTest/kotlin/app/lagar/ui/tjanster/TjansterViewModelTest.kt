package app.lagar.ui.tjanster

import app.lagar.data.GeoRepository
import app.lagar.data.ServiceCatalog
import app.lagar.data.ServiceRepository
import app.lagar.data.ServiceSummary
import app.lagar.domain.LoadState
import app.lagar.domain.Locality
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

@OptIn(ExperimentalCoroutinesApi::class)
class TjansterViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private val geo = GeoRepository {
        """
        {"regions": [{"code": "01", "name": "Stockholms län"}],
         "kommuner": [{"code": "0180", "name": "Stockholm", "regionCode": "01", "website": "https://start.stockholm/"},
                      {"code": "0181", "name": "Södertälje", "regionCode": "01"}]}
        """.encodeToByteArray()
    }

    private class FakeServices(var fail: Boolean = false) : ServiceRepository {
        override suspend fun serviceCatalog(): ServiceCatalog {
            if (fail) error("offline")
            return ServiceCatalog(sampleServices.size, sampleServices)
        }

        override suspend fun servicesForNorm(id: String): List<ServiceSummary> = emptyList()
    }

    @Test
    fun labelsTemplatesWithTheChosenLocalityAndFollowsChanges() {
        val preferences = UserPreferences(MapSettings())
        val viewModel = TjansterViewModel(FakeServices(), preferences, geo)
        val before = assertIs<LoadState.Loaded<List<ServiceEntry>>>(viewModel.state.value).value
        assertEquals(ServicePlace.Kommun(null), before.single { it.service.id == "service-bygglov" }.place)

        preferences.setLocality(Locality("01", "0180"))
        val after = assertIs<LoadState.Loaded<List<ServiceEntry>>>(viewModel.state.value).value
        assertEquals(ServicePlace.Kommun("Stockholm", "https://start.stockholm/"), after.single { it.service.id == "service-bygglov" }.place)
        assertEquals(ServicePlace.Region("Stockholms län"), after.single { it.service.id == "service-vardgaranti" }.place)
    }

    @Test
    fun aKommunWithoutWebsiteGivesNoLink() {
        val preferences = UserPreferences(MapSettings())
        preferences.setLocality(Locality("01", "0181"))
        val viewModel = TjansterViewModel(FakeServices(), preferences, geo)
        val entries = assertIs<LoadState.Loaded<List<ServiceEntry>>>(viewModel.state.value).value
        assertEquals(ServicePlace.Kommun("Södertälje", null), entries.single { it.service.id == "service-bygglov" }.place)
    }

    @Test
    fun failsAndRetries() {
        val services = FakeServices(fail = true)
        val viewModel = TjansterViewModel(services, UserPreferences(MapSettings()), geo)
        val failed = assertIs<LoadState.Failed>(viewModel.state.value)
        services.fail = false
        failed.retry()
        assertEquals(4, assertIs<LoadState.Loaded<List<ServiceEntry>>>(viewModel.state.value).value.size)
    }
}
