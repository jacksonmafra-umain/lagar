package app.lagar.designsystem

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import app.lagar.designsystem.generated.LayerKey

/** Document status colors; "in force" is the green of the Region layer, kept in this one place. */
@Immutable
class StatusColors(darkTheme: Boolean) {
    private val layers = LayerColors(darkTheme)

    /** The status dot (never text). */
    val inForce: Color = layers.accent(LayerKey.Region)

    /** Text next to the dot, AA-safe on the surface. */
    val onInForce: Color = layers.onTint(LayerKey.Region)
}
