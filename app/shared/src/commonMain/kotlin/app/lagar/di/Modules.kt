package app.lagar.di

import app.lagar.data.ApiSource
import app.lagar.data.CachingRepository
import app.lagar.data.Catalog
import app.lagar.data.DataSourceConfig
import app.lagar.data.GeoRepository
import app.lagar.data.HttpRepository
import app.lagar.data.LagarRepository
import app.lagar.data.MinistryRepository
import app.lagar.data.SampleRepository
import app.lagar.domain.SearchQuery
import app.lagar.settings.BookmarkStore
import app.lagar.settings.UserPreferences
import app.lagar.ui.hierarki.HierarkiViewModel
import app.lagar.ui.hierarki.MinistriesViewModel
import app.lagar.ui.home.HomeViewModel
import app.lagar.ui.list.LayerListViewModel
import app.lagar.ui.list.MinistryFilter
import app.lagar.ui.onboarding.OnboardingViewModel
import app.lagar.ui.reader.ReaderViewModel
import app.lagar.ui.search.SearchViewModel
import com.russhwolf.settings.Settings
import io.ktor.client.HttpClient
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import org.koin.core.module.dsl.viewModel
import org.koin.dsl.module

/** A stalled server must reach the error state rather than spin forever. */
private const val REQUEST_TIMEOUT_MS = 15_000L
private const val CONNECT_TIMEOUT_MS = 10_000L

fun appModule(config: DataSourceConfig) = module {
    single {
        HttpClient {
            install(HttpTimeout) {
                requestTimeoutMillis = REQUEST_TIMEOUT_MS
                connectTimeoutMillis = CONNECT_TIMEOUT_MS
            }
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        }
    }
    single<ApiSource> { if (config.useSample) SampleRepository() else HttpRepository(get(), config.baseUrl) }
    single<LagarRepository> { CachingRepository(get<ApiSource>()) }
    single<MinistryRepository> { get<ApiSource>() }
    single { Settings() }
    single { UserPreferences(get()) }
    single { BookmarkStore(get()) }
    single { GeoRepository() }
    single { Catalog(get()) }
    viewModel { HierarkiViewModel(get()) }
    viewModel { HomeViewModel(get(), get(), get(), get()) }
    viewModel { OnboardingViewModel(get(), get()) }
    viewModel { (layer: String, type: String?, ministry: MinistryFilter?) -> LayerListViewModel(get(), layer, type, ministry, get()) }
    viewModel { (layer: String, type: String) -> MinistriesViewModel(get(), layer, type) }
    viewModel { (id: String) -> ReaderViewModel(get(), get(), id) }
    viewModel { (initial: SearchQuery) -> SearchViewModel(get(), get(), initial) }
}
