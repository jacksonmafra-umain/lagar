package app.lagar.ui.reader

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.reader_settings_reset
import app.lagar.resources.reader_text_size_value
import app.lagar.resources.speech_note
import app.lagar.resources.speech_pitch
import app.lagar.resources.speech_rate
import app.lagar.resources.speech_sample
import app.lagar.resources.speech_settings
import app.lagar.resources.speech_voice
import app.lagar.resources.speech_volume
import app.lagar.settings.SpeechSettings
import app.lagar.speech.SpeechVoice
import app.lagar.speech.pick
import app.lagar.ui.common.GlassBottomSheet
import org.jetbrains.compose.resources.stringResource

/**
 * The read-aloud settings: which Swedish voice reads, and its speed, pitch and volume. Every change is kept on the device
 * by [onChange] and heard at once, from the start of the text being read, or through [onSample] when nothing is.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun SpeechSettingsSheet(
    settings: SpeechSettings,
    voices: List<SpeechVoice>,
    onChange: ((SpeechSettings) -> SpeechSettings) -> Unit,
    onReset: () -> Unit,
    onSample: () -> Unit,
    onDismiss: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    GlassBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .verticalScroll(rememberScrollState())
                .padding(start = spacing.marginMobile, end = spacing.marginMobile, bottom = bottom + spacing.lg),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = stringResource(Res.string.speech_settings),
                    style = LagarTheme.type.headlineMd,
                    color = LagarTheme.colors.onSurface,
                    modifier = Modifier.weight(1f).semantics { heading() },
                )
                TextButton(onClick = onReset, enabled = !settings.isDefault) {
                    Text(stringResource(Res.string.reader_settings_reset), style = LagarTheme.type.labelMd)
                }
            }
            Text(stringResource(Res.string.speech_note), style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurfaceVariant)

            if (voices.isNotEmpty()) {
                Group(Res.string.speech_voice) {
                    Options(
                        options = voices,
                        selected = voices.pick(settings.voiceId) ?: voices.first(),
                        label = { it.name },
                        onSelect = { voice -> onChange { it.copy(voiceId = voice.id) } },
                    )
                }
            }

            PercentStepper(
                label = stringResource(Res.string.speech_rate),
                value = settings.rate,
                min = SpeechSettings.MIN_RATE,
                max = SpeechSettings.MAX_RATE,
                onStep = { step -> onChange { it.copy(rate = it.rate + step) } },
            )
            PercentStepper(
                label = stringResource(Res.string.speech_pitch),
                value = settings.pitch,
                min = SpeechSettings.MIN_PITCH,
                max = SpeechSettings.MAX_PITCH,
                onStep = { step -> onChange { it.copy(pitch = it.pitch + step) } },
            )
            PercentStepper(
                label = stringResource(Res.string.speech_volume),
                value = settings.volume,
                min = SpeechSettings.MIN_VOLUME,
                max = SpeechSettings.MAX_VOLUME,
                onStep = { step -> onChange { it.copy(volume = it.volume + step) } },
            )

            TextButton(onClick = onSample) {
                Text(stringResource(Res.string.speech_sample), style = LagarTheme.type.labelMd)
            }
        }
    }
}

@Composable
private fun PercentStepper(label: String, value: Int, min: Int, max: Int, onStep: (Int) -> Unit) {
    Stepper(
        label = label,
        value = "$value %",
        valueDescription = stringResource(Res.string.reader_text_size_value, value),
        canDecrease = value > min,
        canIncrease = value < max,
        onDecrease = { onStep(-SpeechSettings.STEP) },
        onIncrease = { onStep(SpeechSettings.STEP) },
    )
}
