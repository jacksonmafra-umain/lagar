package app.lagar.designsystem

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue

// Browsers without the media feature treat the query as not matching, so they keep the glass.
private fun reduceTransparencyQuery(): JsAny = js("window.matchMedia('(prefers-reduced-transparency: reduce)')")

private fun queryMatches(query: JsAny): Boolean = js("query.matches")

private fun addChangeListener(query: JsAny, handler: (Boolean) -> Unit): JsAny = js(
    """{
    const listener = (e) => handler(e.matches);
    query.addEventListener('change', listener);
    return listener;
}""",
)

private fun removeChangeListener(query: JsAny, listener: JsAny): Unit = js("query.removeEventListener('change', listener)")

@Composable
internal actual fun systemReduceTransparency(): Boolean {
    val query = remember { reduceTransparencyQuery() }
    var enabled by remember { mutableStateOf(queryMatches(query)) }
    DisposableEffect(query) {
        val listener = addChangeListener(query) { enabled = it }
        onDispose { removeChangeListener(query, listener) }
    }
    return enabled
}
