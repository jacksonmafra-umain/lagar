package app.lagar.ui.onboarding

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.lagar.data.LagarRepository
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.ic_layer_crown
import app.lagar.resources.splash_tagline
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

private const val CREEP_TARGET = 0.85f
private const val CREEP_MS = 1_500
private const val FINISH_MS = 200
private val LogoCardSize = 128.dp

/**
 * Loads the API index and calls [onLoaded] once it has finished, whether it worked or not: the index is
 * only warmed here, and Home reports a failed load itself.
 */
@Composable
fun SplashRoute(onLoaded: () -> Unit) {
    val repository = koinInject<LagarRepository>()
    val progress = remember { Animatable(0f) }
    val done = rememberUpdatedState(onLoaded)
    LaunchedEffect(Unit) {
        coroutineScope {
            // Progress is cosmetic: it creeps toward CREEP_TARGET, then fills when the index arrives.
            val creep = launch { progress.animateTo(CREEP_TARGET, tween(CREEP_MS, easing = LinearEasing)) }
            try {
                repository.index()
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // Handled on Home.
            }
            creep.cancel()
            progress.animateTo(1f, tween(FINISH_MS, easing = LinearEasing))
        }
        done.value()
    }
    SplashScreen(progress = { progress.value })
}

@Composable
fun SplashScreen(progress: () -> Float) {
    val colors = LagarTheme.colors
    Box(modifier = Modifier.fillMaxSize().background(colors.surface), contentAlignment = Alignment.Center) {
        Column(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.xl),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        ) {
            // The Stitch logo vessel: a tier 1 glass card holding the crown.
            Box(
                modifier = Modifier.size(LogoCardSize).glass(GlassTier.Card, shape = RoundedCornerShape(RadiusTokens.xl)),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier.size(96.dp).clip(CircleShape).background(colors.primary),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(painterResource(Res.drawable.ic_layer_crown), contentDescription = null, tint = colors.onPrimary, modifier = Modifier.size(56.dp))
                }
            }
            Text(stringResource(Res.string.app_name), style = LagarTheme.type.displayLgMobile, color = colors.primary)
            Text(
                stringResource(Res.string.splash_tagline),
                style = LagarTheme.type.bodyUi,
                color = colors.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            // The bar is cosmetic (it creeps, then fills), so screen readers skip it instead of announcing a made-up percentage.
            LinearProgressIndicator(
                progress = progress,
                modifier = Modifier.width(160.dp).padding(top = LagarTheme.spacing.md).clearAndSetSemantics {},
                color = colors.primary,
                trackColor = colors.surfaceContainerHigh,
            )
        }
    }
}
