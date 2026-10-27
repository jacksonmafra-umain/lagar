package app.lagar.di

import app.lagar.data.DataSourceConfig
import app.lagar.data.HttpRepository
import app.lagar.data.LagarRepository
import app.lagar.data.SampleRepository
import app.lagar.settings.UserPreferences
import com.russhwolf.settings.Settings
import io.ktor.client.HttpClient
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import org.koin.dsl.module

fun appModule(config: DataSourceConfig) = module {
    single {
        HttpClient {
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        }
    }
    single<LagarRepository> {
        if (config.useSample) SampleRepository() else HttpRepository(get(), config.baseUrl)
    }
    single { UserPreferences(Settings()) }
}
