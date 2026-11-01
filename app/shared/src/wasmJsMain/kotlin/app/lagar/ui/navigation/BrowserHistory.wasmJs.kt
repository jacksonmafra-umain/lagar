package app.lagar.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.ExperimentalBrowserHistoryApi
import androidx.navigation.NavHostController
import androidx.navigation.bindToBrowserNavigation

@OptIn(ExperimentalBrowserHistoryApi::class)
@Composable
internal actual fun BrowserHistoryEffect(navController: NavHostController) {
    LaunchedEffect(navController) {
        navController.bindToBrowserNavigation { entry -> entry.webRoute()?.let(::webPath)?.let { "#$it" } ?: "" }
    }
}
