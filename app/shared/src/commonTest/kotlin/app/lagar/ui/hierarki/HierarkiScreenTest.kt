package app.lagar.ui.hierarki

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.ComposeUiTest
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.runComposeUiTest
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.ui.IgnoreOnWasm
import app.lagar.ui.UiTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@IgnoreOnWasm
@OptIn(ExperimentalTestApi::class)
class HierarkiScreenTest : UiTest() {
    private val summaries = DisplayLayer.entries.map { layer ->
        LayerSummary(layer, if (layer == DisplayLayer.Service) 12 else 5)
    }

    /** Shows the layer list in the English UI and waits until the service row's count, a string resource, is drawn. */
    private fun ComposeUiTest.show(onLayerClick: (LayerSummary) -> Unit, onOpenServices: () -> Unit) {
        setContent {
            LagarTheme(darkTheme = false) {
                Box(Modifier.wrapContentSize(Alignment.TopStart, unbounded = true).requiredSize(width = 400.dp, height = 2400.dp)) {
                    HierarkiScreen(LoadState.Loaded(summaries), onLayerClick = onLayerClick, onOpenServices = onOpenServices)
                }
            }
        }
        waitUntil(timeoutMillis = RESOURCE_TIMEOUT_MS) { onAllNodesWithText("12 services").fetchSemanticsNodes().isNotEmpty() }
    }

    @Test
    fun theServiceRowShowsTheServiceCountAndOpensTjanster() = runComposeUiTest {
        val clicked = mutableListOf<DisplayLayer>()
        var servicesOpened = 0
        show(onLayerClick = { clicked += it.layer }, onOpenServices = { servicesOpened++ })
        onNodeWithText("9. Services").performScrollTo().performClick()
        assertEquals(1, servicesOpened)
        assertTrue(clicked.isEmpty())
    }

    @Test
    fun otherLevelsStillOpenTheirDocuments() = runComposeUiTest {
        val clicked = mutableListOf<DisplayLayer>()
        var servicesOpened = 0
        show(onLayerClick = { clicked += it.layer }, onOpenServices = { servicesOpened++ })
        onNodeWithText("2. Acts").performScrollTo().performClick()
        assertEquals(listOf(DisplayLayer.SfsAct), clicked)
        assertEquals(0, servicesOpened)
    }
}

private const val RESOURCE_TIMEOUT_MS = 10_000L
