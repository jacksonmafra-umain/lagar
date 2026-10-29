package app.lagar.ui.reader

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember

private fun canWebShare(): Boolean = js("typeof navigator.share === 'function'")

private fun webShare(title: String, url: String): Unit = js("navigator.share({ title: title, url: url }).catch(function () {})")

private fun canCopy(): Boolean = js("!!(navigator.clipboard && navigator.clipboard.writeText)")

private fun copyText(text: String): Unit = js("navigator.clipboard.writeText(text).catch(function () {})")

private fun pageUrl(): String = js("window.location.origin + window.location.pathname")

@Composable
internal actual fun rememberLinkSharer(): LinkSharer = remember {
    LinkSharer { title, url ->
        when {
            canWebShare() -> {
                webShare(title, url)
                ShareOutcome.Opened
            }
            canCopy() -> {
                copyText(url)
                ShareOutcome.Copied
            }
            else -> ShareOutcome.Failed
        }
    }
}

internal actual fun shareBaseUrl(): String = pageUrl()
