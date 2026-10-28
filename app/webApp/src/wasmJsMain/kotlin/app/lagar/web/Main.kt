package app.lagar.web

import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.window.ComposeViewport
import app.lagar.App
import app.lagar.data.DataSourceConfig

private fun sampleRequested(): Boolean = js("new URLSearchParams(window.location.search).has('sample')")

/**
 * Reads the API from `api/v1/` next to the page, the layout GitHub Pages publishes
 * (`/lagar/` and `/lagar/api/v1/`). Opening the page with `?sample` uses the bundled sample instead.
 */
@OptIn(ExperimentalComposeUiApi::class)
fun main() {
    val config = DataSourceConfig(useSample = sampleRequested(), baseUrl = "api/v1/")
    ComposeViewport { App(config) }
}
