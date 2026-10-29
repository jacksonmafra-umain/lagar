package app.lagar.ui.common

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState

private fun browserPlatform(): String =
    js("(navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || ''")

// Listens in the capture phase so the shortcut works wherever focus is, and cancels the browser's own Ctrl+K.
private fun addKeyListener(handler: (String, Boolean, Boolean, Boolean, Boolean) -> Boolean): JsAny = js(
    """{
    const listener = (e) => { if (handler(e.key || '', e.metaKey, e.ctrlKey, e.altKey, e.shiftKey)) e.preventDefault(); };
    window.addEventListener('keydown', listener, true);
    return listener;
}""",
)

private fun removeKeyListener(listener: JsAny): Unit = js("window.removeEventListener('keydown', listener, true)")

private val keys: ShortcutKeys by lazy { shortcutKeysFor(browserPlatform()) }

internal actual fun searchShortcutKeys(): ShortcutKeys? = keys

@Composable
internal actual fun SearchShortcutEffect(onTrigger: () -> Unit) {
    val trigger by rememberUpdatedState(onTrigger)
    DisposableEffect(Unit) {
        val listener = addKeyListener { key, meta, ctrl, alt, shift ->
            isSearchShortcut(KeyPress(key, meta = meta, ctrl = ctrl, alt = alt, shift = shift), keys).also { if (it) trigger() }
        }
        onDispose { removeKeyListener(listener) }
    }
}
