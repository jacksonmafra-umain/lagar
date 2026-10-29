package app.lagar.ui.onboarding

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingPage
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.settings.UserFocus
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
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class OnboardingViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private object FakeRepository : LagarRepository {
        override suspend fun index() = ApiIndex(1, "2026-01-01T00:00:00Z", listOf(ApiLayer("sfs", 6, listOf(ApiSeries("act", 6)))))

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage = error("unused")

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    private fun viewModel(settings: MapSettings = MapSettings()) = UserPreferences(settings).let { it to OnboardingViewModel(FakeRepository, it) }

    @Test
    fun choicesStayOutOfPreferencesUntilTheEnd() {
        val (prefs, vm) = viewModel()
        vm.selectFocus(UserFocus.Student)
        vm.selectScope(Scope.Kommun)
        vm.selectRegion("14")
        assertFalse(prefs.onboardingDone.value)
        assertEquals(UserFocus.Citizen, prefs.focus.value)
        assertEquals(Scope.Nationell, prefs.scope.value)
    }

    @Test
    fun finishStoresEveryChoice() {
        val (prefs, vm) = viewModel()
        vm.selectFocus(UserFocus.Lawyer)
        vm.selectScope(Scope.Kommun)
        vm.selectRegion("14")
        vm.selectKommun("1480")
        vm.finish()
        assertTrue(prefs.onboardingDone.value)
        assertEquals(UserFocus.Lawyer, prefs.focus.value)
        assertEquals(Scope.Kommun, prefs.scope.value)
        assertEquals(Locality("14", "1480"), prefs.locality.value)
    }

    @Test
    fun skipWithoutChoicesStoresDefaults() {
        val settings = MapSettings()
        val (_, vm) = viewModel(settings)
        vm.skip()
        val reopened = UserPreferences(settings)
        assertTrue(reopened.onboardingDone.value)
        assertEquals(Scope.Nationell, reopened.scope.value)
        assertEquals(Locality(null, null), reopened.locality.value)
        assertEquals(UserFocus.Citizen, reopened.focus.value)
    }

    @Test
    fun skipFromALaterStepDropsScopeAndLocalityButKeepsFocus() {
        val (prefs, vm) = viewModel()
        vm.selectFocus(UserFocus.Student)
        vm.selectScope(Scope.Region)
        vm.selectRegion("01")
        vm.skip()
        assertTrue(prefs.onboardingDone.value)
        assertEquals(Scope.Nationell, prefs.scope.value)
        assertEquals(Locality(null, null), prefs.locality.value)
        assertEquals(UserFocus.Student, prefs.focus.value)
    }

    @Test
    fun startsFromTheStoredFocus() {
        val (_, vm) = viewModel(MapSettings("focus" to "Lawyer"))
        assertEquals(UserFocus.Lawyer, vm.focus.value)
    }

    @Test
    fun loadsCountsPerScope() {
        val (_, vm) = viewModel()
        assertEquals(6, vm.counts.value?.get(Scope.Nationell))
    }
}
