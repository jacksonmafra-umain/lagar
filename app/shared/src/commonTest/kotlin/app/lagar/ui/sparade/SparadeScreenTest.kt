package app.lagar.ui.sparade

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.ComposeUiTest
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.runComposeUiTest
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.settings.Bookmark
import app.lagar.settings.BookmarkStore
import app.lagar.settings.SavedService
import app.lagar.ui.IgnoreOnWasm
import app.lagar.ui.UiTest
import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@IgnoreOnWasm
@OptIn(ExperimentalTestApi::class)
class SparadeScreenTest : UiTest() {
    private val act = Bookmark("sfs-1962-700", "Brottsbalk (1962:700)", "1962:700", "act", "sfs")
    private val parental = SavedService("service-foraldrapenning", "Föräldrapenning", "Försäkringskassan")

    /**
     * Shows Sparade over [store] in the English UI, removing entries the way the route does, and waits until the
     * remove button's description, a string resource, is drawn.
     */
    private fun ComposeUiTest.show(
        store: BookmarkStore,
        onOpen: (String, String?) -> Unit = { _, _ -> },
        onOpenService: (String) -> Unit = {},
    ) {
        setContent {
            LagarTheme(darkTheme = false) {
                Box(Modifier.wrapContentSize(Alignment.TopStart, unbounded = true).requiredSize(width = 400.dp, height = 1200.dp)) {
                    val bookmarks by store.bookmarks.collectAsState()
                    val services by store.services.collectAsState()
                    SparadeScreen(
                        bookmarks = bookmarks,
                        provisions = emptyList(),
                        notes = emptyList(),
                        services = services,
                        onOpen = onOpen,
                        onOpenService = onOpenService,
                        onRemove = { entry ->
                            when (entry) {
                                is SavedEntry.Service -> store.removeService(entry.service.id)?.let { removed -> { store.restoreService(removed) } }
                                is SavedEntry.Document -> store.remove(entry.document.id)?.let { removed -> { store.restore(removed) } }
                                else -> null
                            }
                        },
                    )
                }
            }
        }
        waitUntil(timeoutMillis = RESOURCE_TIMEOUT_MS) {
            onAllNodesWithContentDescription("Remove Föräldrapenning from saved").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun aSavedServiceIsListedAndOpensItsDetail() = runComposeUiTest {
        val store = BookmarkStore(MapSettings()).apply {
            toggle(act)
            toggleService(parental)
        }
        val opened = mutableListOf<String>()
        show(store, onOpenService = { opened += it })
        onNodeWithText("Försäkringskassan").assertExists()
        onNodeWithText("Brottsbalk (1962:700)").assertExists()
        onNodeWithText("Föräldrapenning").performClick()
        assertEquals(listOf("service-foraldrapenning"), opened)
    }

    @Test
    fun removingASavedServiceKeepsTheDocuments() = runComposeUiTest {
        val store = BookmarkStore(MapSettings()).apply {
            toggle(act)
            toggleService(parental)
        }
        show(store)
        onNodeWithContentDescription("Remove Föräldrapenning from saved").performClick()
        waitForIdle()
        assertTrue(store.services.value.isEmpty())
        assertEquals(listOf(act), store.bookmarks.value)
        assertTrue(onAllNodesWithText("Föräldrapenning").fetchSemanticsNodes().isEmpty())
    }

    @Test
    fun theServicesFilterShowsOnlyServices() = runComposeUiTest {
        val store = BookmarkStore(MapSettings()).apply {
            toggle(act)
            toggleService(parental)
        }
        show(store)
        // The filter pill (a tab), not the level heading: both read SERVICES.
        onNode(hasText("SERVICES") and SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Tab)).performClick()
        onNodeWithText("Föräldrapenning").assertExists()
        assertTrue(onAllNodesWithText("Brottsbalk (1962:700)").fetchSemanticsNodes().isEmpty())
    }
}

private const val RESOURCE_TIMEOUT_MS = 10_000L
