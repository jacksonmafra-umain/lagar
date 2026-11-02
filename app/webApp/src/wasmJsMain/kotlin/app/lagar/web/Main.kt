package app.lagar.web

import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.window.ComposeViewport
import app.lagar.App
import app.lagar.data.DataSourceConfig
import app.lagar.ui.navigation.parseReaderLink
import app.lagar.ui.navigation.parseWebPath

private fun sampleRequested(): Boolean = js("new URLSearchParams(window.location.search).has('sample')")

private fun locationSearch(): String = js("window.location.search")

private fun locationHash(): String = js("window.location.hash")

// The back stack the history saved for this page (route strings, one per line); empty on a fresh visit.
private fun historyState(): String = js("typeof window.history.state === 'string' ? window.history.state : ''")

/**
 * Reads the API from `api/v1/` next to the page, the layout GitHub Pages publishes
 * (`/lagar/` and `/lagar/api/v1/`). Opening the page with `?sample` uses the bundled sample instead.
 * The screen in the address fragment (`#/reader/<id>?p=<anchor>`, kept up to date while browsing) opens after the
 * splash, and a reload rebuilds the back stack the history saved; an older shared link (`?doc=<id>&p=<anchor>`) opens
 * that document.
 */
@OptIn(ExperimentalComposeUiApi::class)
fun main() {
    val config = DataSourceConfig(useSample = sampleRequested(), baseUrl = "api/v1/")
    val start = parseWebPath(locationHash()) ?: parseReaderLink(locationSearch())
    val stack = historyState().lines().filter { it.isNotBlank() }
    ComposeViewport { App(config, startRoute = start, startStack = stack) }
}
