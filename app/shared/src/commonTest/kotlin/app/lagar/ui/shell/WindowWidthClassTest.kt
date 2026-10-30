package app.lagar.ui.shell

import androidx.compose.ui.unit.dp
import kotlin.test.Test
import kotlin.test.assertEquals

class WindowWidthClassTest {
    @Test
    fun phonesInPortraitAreCompact() {
        assertEquals(WindowWidthClass.Compact, WindowWidthClass.of(375.dp))
        assertEquals(WindowWidthClass.Compact, WindowWidthClass.of(599.dp))
    }

    @Test
    fun tabletsAreMedium() {
        assertEquals(WindowWidthClass.Medium, WindowWidthClass.of(600.dp))
        assertEquals(WindowWidthClass.Medium, WindowWidthClass.of(768.dp))
        assertEquals(WindowWidthClass.Medium, WindowWidthClass.of(1023.dp))
    }

    @Test
    fun desktopIsExpanded() {
        assertEquals(WindowWidthClass.Expanded, WindowWidthClass.of(1024.dp))
        assertEquals(WindowWidthClass.Expanded, WindowWidthClass.of(1440.dp))
    }
}
