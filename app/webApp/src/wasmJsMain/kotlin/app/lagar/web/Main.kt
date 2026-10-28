package app.lagar.web

import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.window.ComposeViewport
import app.lagar.App
import app.lagar.data.DataSourceConfig

private fun apiRequested(): Boolean = js("new URLSearchParams(window.location.search).has('api')")

/**
 * The bundled sample is the default. Opening the page with `?api` reads the API from `../api/v1/`,
 * i.e. the same server root that hosts the app under `/lagar/`.
 */
@OptIn(ExperimentalComposeUiApi::class)
fun main() {
    val config = DataSourceConfig(useSample = !apiRequested(), baseUrl = "../api/v1/")
    ComposeViewport { App(config) }
}
