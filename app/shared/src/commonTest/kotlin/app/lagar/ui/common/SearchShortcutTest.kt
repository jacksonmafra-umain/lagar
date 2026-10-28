package app.lagar.ui.common

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SearchShortcutTest {
    private fun press(
        key: String = "k",
        meta: Boolean = false,
        ctrl: Boolean = false,
        alt: Boolean = false,
        shift: Boolean = false,
        keys: ShortcutKeys,
    ) = isSearchShortcut(KeyPress(key, meta = meta, ctrl = ctrl, alt = alt, shift = shift), keys)

    @Test
    fun appleUsesCommandK() {
        assertTrue(press(meta = true, keys = ShortcutKeys.Apple))
        assertFalse(press(ctrl = true, keys = ShortcutKeys.Apple))
    }

    @Test
    fun otherPlatformsUseCtrlK() {
        assertTrue(press(ctrl = true, keys = ShortcutKeys.Other))
        assertFalse(press(meta = true, keys = ShortcutKeys.Other))
    }

    @Test
    fun capsLockStillMatches() {
        assertTrue(press(key = "K", ctrl = true, keys = ShortcutKeys.Other))
    }

    @Test
    fun otherKeysAndExtraModifiersDoNotMatch() {
        assertFalse(press(key = "j", ctrl = true, keys = ShortcutKeys.Other))
        assertFalse(press(key = "k", keys = ShortcutKeys.Other))
        assertFalse(press(ctrl = true, shift = true, keys = ShortcutKeys.Other))
        assertFalse(press(ctrl = true, alt = true, keys = ShortcutKeys.Other))
        assertFalse(press(meta = true, ctrl = true, keys = ShortcutKeys.Apple))
    }

    @Test
    fun applePlatformsAreDetected() {
        assertEquals(ShortcutKeys.Apple, shortcutKeysFor("MacIntel"))
        assertEquals(ShortcutKeys.Apple, shortcutKeysFor("macOS"))
        assertEquals(ShortcutKeys.Apple, shortcutKeysFor("iPad"))
        assertEquals(ShortcutKeys.Other, shortcutKeysFor("Win32"))
        assertEquals(ShortcutKeys.Other, shortcutKeysFor("Linux x86_64"))
        assertEquals(ShortcutKeys.Other, shortcutKeysFor(""))
    }
}
