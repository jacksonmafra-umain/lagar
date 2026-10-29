package app.lagar.designsystem

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import platform.Foundation.NSNotificationCenter
import platform.Foundation.NSOperationQueue
import platform.UIKit.UIAccessibilityIsReduceTransparencyEnabled
import platform.UIKit.UIAccessibilityReduceTransparencyStatusDidChangeNotification

@Composable
internal actual fun systemReduceTransparency(): Boolean {
    var enabled by remember { mutableStateOf(UIAccessibilityIsReduceTransparencyEnabled()) }
    DisposableEffect(Unit) {
        val center = NSNotificationCenter.defaultCenter
        val observer = center.addObserverForName(
            name = UIAccessibilityReduceTransparencyStatusDidChangeNotification,
            `object` = null,
            queue = NSOperationQueue.mainQueue,
        ) { _ -> enabled = UIAccessibilityIsReduceTransparencyEnabled() }
        onDispose { center.removeObserver(observer) }
    }
    return enabled
}
