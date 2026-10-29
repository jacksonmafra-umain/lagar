package app.lagar.ui.reader

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import app.lagar.ui.navigation.WEB_APP_URL

@Composable
internal actual fun rememberLinkSharer(): LinkSharer {
    val context = LocalContext.current
    return remember(context) {
        LinkSharer { title, url ->
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_SUBJECT, title)
                putExtra(Intent.EXTRA_TEXT, url)
            }
            val chooser = Intent.createChooser(send, title).apply {
                if (context !is Activity) addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            try {
                context.startActivity(chooser)
                ShareOutcome.Opened
            } catch (_: ActivityNotFoundException) {
                ShareOutcome.Failed
            }
        }
    }
}

internal actual fun shareBaseUrl(): String = WEB_APP_URL
