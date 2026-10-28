package app.lagar

import androidx.compose.ui.window.ComposeUIViewController
import app.lagar.data.DataSourceConfig
import kotlin.experimental.ExperimentalNativeApi
import kotlin.native.Platform

/** Debug builds read the API served from the host machine; release builds read the published API. */
@OptIn(ExperimentalNativeApi::class)
@Suppress("FunctionName")
fun MainViewController() = ComposeUIViewController {
    val baseUrl = if (Platform.isDebugBinary) "http://localhost:8000/api/v1/" else DataSourceConfig.PUBLISHED_API
    App(DataSourceConfig(useSample = false, baseUrl = baseUrl))
}
