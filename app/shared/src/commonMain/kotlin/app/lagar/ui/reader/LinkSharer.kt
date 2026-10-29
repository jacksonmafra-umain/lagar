package app.lagar.ui.reader

import androidx.compose.runtime.Composable

/** What sharing a link did; [Copied] asks the caller to confirm, since nothing else is visible. */
enum class ShareOutcome { Opened, Copied, Failed }

/** Hands a link to the platform: the share sheet on Android and iOS, the Web Share API or the clipboard in a browser. */
fun interface LinkSharer {
    fun share(title: String, url: String): ShareOutcome
}

@Composable
internal expect fun rememberLinkSharer(): LinkSharer

/** Where shared links point: the page itself on the web, the published web app elsewhere. */
internal expect fun shareBaseUrl(): String
