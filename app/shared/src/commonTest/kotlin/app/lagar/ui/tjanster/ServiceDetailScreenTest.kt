package app.lagar.ui.tjanster

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.test.ComposeUiTest
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.runComposeUiTest
import androidx.compose.ui.unit.dp
import app.lagar.data.ServiceNormRef
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.LoadState
import app.lagar.ui.IgnoreOnWasm
import app.lagar.ui.UiTest
import kotlin.test.Test
import kotlin.test.assertEquals

@IgnoreOnWasm
@OptIn(ExperimentalTestApi::class)
class ServiceDetailScreenTest : UiTest() {
    private val lead = "Föräldrapenning kan du få för att vara hemma med ditt barn i stället för att arbeta."

    private val foraldrapenning = service("service-foraldrapenning", "Föräldrapenning", "Försäkringskassan").copy(
        basedOn = listOf(
            ServiceNormRef("sfs-2010-110", "Socialförsäkringsbalk (2010:110)", "act", "sfs"),
            ServiceNormRef("sfs-1962-381", "Lag (1962:381) om allmän försäkring", "act", "sfs", repealed = "2011-01-01"),
        ),
    )

    private class RecordingUriHandler : UriHandler {
        val opened = mutableListOf<String>()

        override fun openUri(uri: String) {
            opened += uri
        }
    }

    /** Shows [detail] in the English UI and waits until the button label, a string resource, is drawn. */
    private fun ComposeUiTest.show(
        detail: ServiceDetail,
        uriHandler: UriHandler = RecordingUriHandler(),
        onOpenDocument: (String) -> Unit = {},
    ) {
        setContent {
            LagarTheme(darkTheme = false) {
                CompositionLocalProvider(LocalUriHandler provides uriHandler) {
                    Box(
                        Modifier
                            .wrapContentSize(Alignment.TopStart, unbounded = true)
                            .requiredSize(width = 400.dp, height = 1600.dp),
                    ) { ServiceDetailScreen(LoadState.Loaded(detail), onBack = {}, onOpenDocument = onOpenDocument) }
                }
            }
        }
        waitUntil(timeoutMillis = RESOURCE_TIMEOUT_MS) {
            onAllNodesWithText("Go to the service").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun titleAndLeadStaySwedishInTheEnglishUi() = runComposeUiTest {
        show(ServiceDetail(foraldrapenning, lead, "2026-11-13"))
        onNodeWithText("Föräldrapenning").assertExists()
        onNodeWithText(lead).assertExists()
        onNodeWithText("Försäkringskassan").assertExists()
        onNodeWithText("Based on").assertExists()
        onNodeWithText("Read from the official page on 2026-11-13").assertExists()
    }

    @Test
    fun tappingANormOpensItInTheReader() = runComposeUiTest {
        val opened = mutableListOf<String>()
        show(ServiceDetail(foraldrapenning, lead, null), onOpenDocument = { opened += it })
        onNodeWithText("Socialförsäkringsbalk (2010:110)").performClick()
        assertEquals(listOf("sfs-2010-110"), opened)
    }

    @Test
    fun aRepealedNormSaysSo() = runComposeUiTest {
        show(ServiceDetail(foraldrapenning, lead, null))
        onNodeWithText("Repealed on 2011-01-01").assertExists()
    }

    @Test
    fun theButtonOpensTheSourceWithoutAServiceUrl() = runComposeUiTest {
        val handler = RecordingUriHandler()
        show(ServiceDetail(foraldrapenning, lead, null), handler)
        onNodeWithText("Go to the service").performClick()
        assertEquals(listOf("https://example.se/service-foraldrapenning"), handler.opened)
    }

    @Test
    fun theButtonOpensTheServiceUrlWhenSet() = runComposeUiTest {
        val handler = RecordingUriHandler()
        val withStart = foraldrapenning.copy(serviceUrl = "https://e.example.se/foraldrapenning")
        show(ServiceDetail(withStart, lead, null), handler)
        onNodeWithText("Go to the service").performClick()
        assertEquals(listOf("https://e.example.se/foraldrapenning"), handler.opened)
    }

    @Test
    fun aKommunTemplateLinksToTheChosenKommun() = runComposeUiTest {
        val bygglov = service("service-bygglov", "Bygglov", "Kommunen", scope = "municipality", template = true)
        val handler = RecordingUriHandler()
        show(ServiceDetail(bygglov, null, null, ServicePlace.Kommun("Stockholm", "https://start.stockholm/")), handler)
        onNodeWithText("Visit Stockholm").performClick()
        assertEquals(listOf("https://start.stockholm/"), handler.opened)
    }
}

private const val RESOURCE_TIMEOUT_MS = 10_000L
