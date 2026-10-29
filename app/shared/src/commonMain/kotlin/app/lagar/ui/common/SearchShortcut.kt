package app.lagar.ui.common

import androidx.compose.runtime.Composable
import app.lagar.resources.Res
import app.lagar.resources.search_shortcut_apple
import app.lagar.resources.search_shortcut_other
import org.jetbrains.compose.resources.stringResource

/** Which modifier opens search: Command on Apple keyboards, Ctrl elsewhere. */
internal enum class ShortcutKeys { Apple, Other }

/** A key press as the browser reports it: [key] is the produced character, such as `k`. */
internal data class KeyPress(val key: String, val meta: Boolean, val ctrl: Boolean, val alt: Boolean, val shift: Boolean)

/** `⌘K` on Apple keyboards and `Ctrl+K` elsewhere, with no other modifier held. */
internal fun isSearchShortcut(press: KeyPress, keys: ShortcutKeys): Boolean {
    if (!press.key.equals("k", ignoreCase = true) || press.alt || press.shift) return false
    return when (keys) {
        ShortcutKeys.Apple -> press.meta && !press.ctrl
        ShortcutKeys.Other -> press.ctrl && !press.meta
    }
}

/** Picks the modifier from the browser's platform name (`MacIntel`, `macOS`, `iPad`, `Win32`, …). */
internal fun shortcutKeysFor(platform: String): ShortcutKeys {
    val name = platform.lowercase()
    return if (APPLE_PLATFORMS.any { name.startsWith(it) }) ShortcutKeys.Apple else ShortcutKeys.Other
}

private val APPLE_PLATFORMS = listOf("mac", "iphone", "ipad", "ipod")

/** The search shortcut of this platform, or null where there is none (Android and iOS). */
internal expect fun searchShortcutKeys(): ShortcutKeys?

/** Calls [onTrigger] when the search shortcut is pressed; does nothing where there is no shortcut. */
@Composable
internal expect fun SearchShortcutEffect(onTrigger: () -> Unit)

/** The label shown in the search command bar, such as `⌘K`, or null where there is no shortcut. */
@Composable
internal fun searchShortcutHint(): String? = when (searchShortcutKeys()) {
    ShortcutKeys.Apple -> stringResource(Res.string.search_shortcut_apple)
    ShortcutKeys.Other -> stringResource(Res.string.search_shortcut_other)
    null -> null
}
