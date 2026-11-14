package app.lagar.ui.tjanster

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.ComposeUiTest
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.runComposeUiTest
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.LoadState
import app.lagar.ui.IgnoreOnWasm
import app.lagar.ui.UiTest
import kotlin.test.Test
import kotlin.test.assertEquals

@IgnoreOnWasm
@OptIn(ExperimentalTestApi::class)
class TjansterScreenTest : UiTest() {
    private val stockholm = ServiceLocality("01", "Stockholms län", "0180", "Stockholm")

    /**
     * Shows [state] and waits until [ready], a string resource of that state, is drawn: in the browser the resources
     * load asynchronously after the first frame.
     */
    private fun ComposeUiTest.show(state: LoadState<List<ServiceEntry>>, ready: String = "All", onOpen: (String) -> Unit = {}) {
        // Pinned to the top left and tall enough for the lazy list to compose every card of the sample catalogue.
        setContent {
            LagarTheme(darkTheme = false) {
                Box(
                    Modifier
                        .wrapContentSize(Alignment.TopStart, unbounded = true)
                        .requiredSize(width = 400.dp, height = 1600.dp),
                ) { TjansterScreen(state, onOpen) }
            }
        }
        waitUntil(timeoutMillis = RESOURCE_TIMEOUT_MS) { onAllNodesWithText(ready, ignoreCase = true).fetchSemanticsNodes().isNotEmpty() }
    }

    private fun ComposeUiTest.assertShown(vararg titles: String) {
        listOf("Föräldrapenning", "Ansök om F-skatt", "Bygglov", "Vårdgaranti").forEach { title ->
            onAllNodesWithText(title).assertCountEquals(if (title in titles) 1 else 0)
        }
    }

    @Test
    fun listsNationalServicesAndTemplatesNamedAfterTheChosenKommun() = runComposeUiTest {
        show(LoadState.Loaded(serviceEntries(sampleServices, stockholm)))
        assertShown("Föräldrapenning", "Ansök om F-skatt", "Bygglov", "Vårdgaranti")
        onAllNodesWithText("National").assertCountEquals(2)
        onNodeWithText("Stockholm").assertExists()
        onNodeWithText("Stockholms län").assertExists()
    }

    @Test
    fun templatesWithoutAChosenKommunGetANeutralLabel() = runComposeUiTest {
        show(LoadState.Loaded(serviceEntries(sampleServices, ServiceLocality.None)))
        onNodeWithText("Your municipality").assertExists()
        onNodeWithText("Your county").assertExists()
    }

    @Test
    fun filtersByText() = runComposeUiTest {
        show(LoadState.Loaded(serviceEntries(sampleServices, stockholm)))
        onNode(hasSetTextAction()).performTextInput("skatteverket")
        assertShown("Ansök om F-skatt")
    }

    @Test
    fun filtersByTopicAndClearsIt() = runComposeUiTest {
        show(LoadState.Loaded(serviceEntries(sampleServices, stockholm)))
        onNodeWithText("Health and care").performClick()
        assertShown("Vårdgaranti")
        onNodeWithText("Health and care").performClick()
        assertShown("Föräldrapenning", "Ansök om F-skatt", "Bygglov", "Vårdgaranti")
    }

    @Test
    fun filtersByAudience() = runComposeUiTest {
        show(LoadState.Loaded(serviceEntries(sampleServices, stockholm)))
        onNodeWithText("Businesses", ignoreCase = true).performClick()
        assertShown("Ansök om F-skatt", "Bygglov")
    }

    @Test
    fun showsTheNoMatchStateWhenNothingMatches() = runComposeUiTest {
        show(LoadState.Loaded(serviceEntries(sampleServices, stockholm)))
        onNode(hasSetTextAction()).performTextInput("pass")
        onNodeWithText("No matching services").assertExists()
        assertShown()
    }

    @Test
    fun showsTheEmptyStateWithoutServices() = runComposeUiTest {
        show(LoadState.Loaded(emptyList()), ready = "No services yet")
        onNodeWithText("No services yet").assertExists()
    }

    @Test
    fun showsTheErrorStateAndRetries() = runComposeUiTest {
        var retries = 0
        show(LoadState.Failed(retry = { retries++ }), ready = "Try again")
        onNodeWithText("Try again", ignoreCase = true).performClick()
        assertEquals(1, retries)
    }

    @Test
    fun tappingACardOpensItsService() = runComposeUiTest {
        var opened: String? = null
        show(LoadState.Loaded(serviceEntries(sampleServices, stockholm)), onOpen = { opened = it })
        onNodeWithText("Föräldrapenning").performClick()
        assertEquals("service-foraldrapenning", opened)
    }
}

private const val RESOURCE_TIMEOUT_MS = 10_000L
