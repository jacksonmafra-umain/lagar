package app.lagar

import androidx.compose.ui.window.ComposeUIViewController
import app.lagar.data.DataSourceConfig
import kotlin.experimental.ExperimentalNativeApi
import kotlin.native.Platform

/** Debug builds read the API served from the host machine; release builds use the bundled sample. */
@OptIn(ExperimentalNativeApi::class)
@Suppress("FunctionName")
fun MainViewController() = ComposeUIViewController {
    App(DataSourceConfig(useSample = !Platform.isDebugBinary, baseUrl = "http://localhost:8000/api/v1/"))
}
