package app.lagar.ui.reader

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import app.lagar.ui.navigation.WEB_APP_URL
import platform.Foundation.NSURL
import platform.UIKit.UIActivityViewController
import platform.UIKit.UIApplication
import platform.UIKit.UIViewController
import platform.UIKit.popoverPresentationController

@Composable
internal actual fun rememberLinkSharer(): LinkSharer = remember {
    LinkSharer { _, url ->
        val presenter = topViewController() ?: return@LinkSharer ShareOutcome.Failed
        val item: Any = NSURL.URLWithString(url) ?: url
        val sheet = UIActivityViewController(activityItems = listOf(item), applicationActivities = null)
        // On iPad the sheet is a popover and needs an anchor.
        sheet.popoverPresentationController?.sourceView = presenter.view
        presenter.presentViewController(sheet, animated = true, completion = null)
        ShareOutcome.Opened
    }
}

private fun topViewController(): UIViewController? {
    @Suppress("DEPRECATION")
    var top = UIApplication.sharedApplication.keyWindow?.rootViewController ?: return null
    while (true) top = top.presentedViewController ?: return top
}

internal actual fun shareBaseUrl(): String = WEB_APP_URL
