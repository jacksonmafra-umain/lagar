package app.lagar.ui.reader

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.reader_align
import app.lagar.resources.reader_align_justify
import app.lagar.resources.reader_align_start
import app.lagar.resources.reader_bold
import app.lagar.resources.reader_decrease
import app.lagar.resources.reader_font
import app.lagar.resources.reader_font_sans
import app.lagar.resources.reader_font_serif
import app.lagar.resources.reader_increase
import app.lagar.resources.reader_letter_spacing
import app.lagar.resources.reader_line_height
import app.lagar.resources.reader_line_height_value
import app.lagar.resources.reader_paper
import app.lagar.resources.reader_paper_app
import app.lagar.resources.reader_paper_contrast
import app.lagar.resources.reader_paper_dark
import app.lagar.resources.reader_paper_light
import app.lagar.resources.reader_paper_sepia
import app.lagar.resources.reader_settings
import app.lagar.resources.reader_settings_reset
import app.lagar.resources.reader_text_size
import app.lagar.resources.reader_text_size_value
import app.lagar.resources.reader_width
import app.lagar.resources.reader_width_narrow
import app.lagar.resources.reader_width_standard
import app.lagar.resources.reader_width_wide
import app.lagar.settings.ReadingAlign
import app.lagar.settings.ReadingFont
import app.lagar.settings.ReadingPaper
import app.lagar.settings.ReadingSettings
import app.lagar.settings.ReadingWidth
import app.lagar.ui.common.GlassBottomSheet
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

/**
 * The reader's e-reader style settings: paper, font, text size, line and letter spacing, column width, alignment and
 * bold text. Every change applies at once to the text behind the sheet and is kept on the device by [onChange].
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
internal fun ReadingSettingsSheet(settings: ReadingSettings, onChange: ((ReadingSettings) -> ReadingSettings) -> Unit, onReset: () -> Unit, onDismiss: () -> Unit) {
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
                    text = stringResource(Res.string.reader_settings),
                    style = LagarTheme.type.headlineMd,
                    color = LagarTheme.colors.onSurface,
                    modifier = Modifier.weight(1f).semantics { heading() },
                )
                TextButton(onClick = onReset, enabled = !settings.isDefault) {
                    Text(stringResource(Res.string.reader_settings_reset), style = LagarTheme.type.labelMd)
                }
            }

            Group(Res.string.reader_paper) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.sm), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    ReadingPaper.entries.forEach { paper ->
                        PaperSwatch(paper, selected = settings.paper == paper) { onChange { it.copy(paper = paper) } }
                    }
                }
            }

            Group(Res.string.reader_font) {
                Options(
                    options = ReadingFont.entries,
                    selected = settings.font,
                    label = { if (it == ReadingFont.Serif) Res.string.reader_font_serif else Res.string.reader_font_sans },
                    onSelect = { font -> onChange { it.copy(font = font) } },
                )
            }

            val sizeLabel = stringResource(Res.string.reader_text_size)
            Stepper(
                label = sizeLabel,
                value = "${settings.textScale} %",
                valueDescription = stringResource(Res.string.reader_text_size_value, settings.textScale),
                canDecrease = settings.textScale > ReadingSettings.MIN_TEXT_SCALE,
                canIncrease = settings.textScale < ReadingSettings.MAX_TEXT_SCALE,
                onDecrease = { onChange { it.copy(textScale = it.textScale - ReadingSettings.TEXT_SCALE_STEP) } },
                onIncrease = { onChange { it.copy(textScale = it.textScale + ReadingSettings.TEXT_SCALE_STEP) } },
            )
            val lineValue = stringResource(Res.string.reader_line_height_value, settings.lineHeight / 10, settings.lineHeight % 10)
            Stepper(
                label = stringResource(Res.string.reader_line_height),
                value = lineValue,
                valueDescription = lineValue,
                canDecrease = settings.lineHeight > ReadingSettings.MIN_LINE_HEIGHT,
                canIncrease = settings.lineHeight < ReadingSettings.MAX_LINE_HEIGHT,
                onDecrease = { onChange { it.copy(lineHeight = it.lineHeight - 1) } },
                onIncrease = { onChange { it.copy(lineHeight = it.lineHeight + 1) } },
            )
            Stepper(
                label = stringResource(Res.string.reader_letter_spacing),
                value = settings.letterSpacing.toString(),
                valueDescription = settings.letterSpacing.toString(),
                canDecrease = settings.letterSpacing > 0,
                canIncrease = settings.letterSpacing < ReadingSettings.MAX_LETTER_SPACING,
                onDecrease = { onChange { it.copy(letterSpacing = it.letterSpacing - 1) } },
                onIncrease = { onChange { it.copy(letterSpacing = it.letterSpacing + 1) } },
            )

            Group(Res.string.reader_width) {
                Options(
                    options = ReadingWidth.entries,
                    selected = settings.width,
                    label = {
                        when (it) {
                            ReadingWidth.Narrow -> Res.string.reader_width_narrow
                            ReadingWidth.Standard -> Res.string.reader_width_standard
                            ReadingWidth.Wide -> Res.string.reader_width_wide
                        }
                    },
                    onSelect = { width -> onChange { it.copy(width = width) } },
                )
            }

            Group(Res.string.reader_align) {
                Options(
                    options = ReadingAlign.entries,
                    selected = settings.align,
                    label = { if (it == ReadingAlign.Start) Res.string.reader_align_start else Res.string.reader_align_justify },
                    onSelect = { align -> onChange { it.copy(align = align) } },
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = ShellDimens.TouchTarget)
                    .toggleable(value = settings.bold, role = Role.Switch) { bold -> onChange { it.copy(bold = bold) } },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    stringResource(Res.string.reader_bold),
                    style = LagarTheme.type.bodyUi,
                    color = LagarTheme.colors.onSurface,
                    modifier = Modifier.weight(1f),
                )
                Switch(
                    checked = settings.bold,
                    onCheckedChange = null,
                    colors = SwitchDefaults.colors(checkedTrackColor = LagarTheme.colors.primary),
                )
            }
        }
    }
}

@Composable
private fun Group(title: StringResource, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        Text(
            stringResource(title),
            style = LagarTheme.type.labelMd,
            color = LagarTheme.colors.onSurfaceVariant,
            modifier = Modifier.semantics { heading() },
        )
        content()
    }
}

/** A row of pill-shaped choices, one selected; each is a radio button to screen readers. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun <T> Options(options: List<T>, selected: T, label: (T) -> StringResource, onSelect: (T) -> Unit) {
    val colors = LagarTheme.colors
    FlowRow(horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        options.forEach { option ->
            val on = option == selected
            Surface(
                shape = CircleShape,
                color = if (on) colors.primaryContainer else colors.surfaceContainerHigh,
                contentColor = if (on) colors.onPrimaryContainer else colors.onSurface,
                border = BorderStroke(1.dp, if (on) colors.primary else colors.outlineVariant),
                modifier = Modifier
                    .heightIn(min = ShellDimens.TouchTarget)
                    .clip(CircleShape)
                    .selectable(selected = on, role = Role.RadioButton) { onSelect(option) },
            ) {
                Box(Modifier.padding(horizontal = LagarTheme.spacing.md), contentAlignment = Alignment.Center) {
                    Text(stringResource(label(option)), style = LagarTheme.type.labelMd, modifier = Modifier.padding(vertical = 14.dp))
                }
            }
        }
    }
}

/** A setting with a minus and a plus button around its current value. */
@Composable
private fun Stepper(
    label: String,
    value: String,
    valueDescription: String,
    canDecrease: Boolean,
    canIncrease: Boolean,
    onDecrease: () -> Unit,
    onIncrease: () -> Unit,
) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface, modifier = Modifier.weight(1f))
        StepButton("−", stringResource(Res.string.reader_decrease, label), canDecrease, onDecrease)
        Text(
            value,
            style = LagarTheme.type.labelMd,
            color = LagarTheme.colors.onSurface,
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm).semantics { stateDescription = valueDescription },
        )
        StepButton("+", stringResource(Res.string.reader_increase, label), canIncrease, onIncrease)
    }
}

@Composable
private fun StepButton(symbol: String, description: String, enabled: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .border(1.dp, colors.outlineVariant, CircleShape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            symbol,
            style = LagarTheme.type.headlineSm,
            color = if (enabled) colors.onSurface else colors.onSurface.copy(alpha = 0.38f),
        )
    }
}

/** A round sample of a paper with "Aa" in its ink over its name; the selected one has a thick ring in the primary color. */
@Composable
private fun PaperSwatch(paper: ReadingPaper, selected: Boolean, onClick: () -> Unit) {
    val app = LagarTheme.colors
    val appDark = LagarTheme.isDark
    val scheme = remember(paper, app, appDark) { paper.scheme(app, appDark) }
    val name = when (paper) {
        ReadingPaper.App -> Res.string.reader_paper_app
        ReadingPaper.Light -> Res.string.reader_paper_light
        ReadingPaper.Sepia -> Res.string.reader_paper_sepia
        ReadingPaper.Dark -> Res.string.reader_paper_dark
        ReadingPaper.HighContrast -> Res.string.reader_paper_contrast
    }
    Column(
        modifier = Modifier
            .clip(MaterialTheme.shapes.medium)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(LagarTheme.spacing.xs),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
    ) {
        Box(
            modifier = Modifier
                .size(ShellDimens.TouchTarget)
                .clip(CircleShape)
                .background(scheme.surface)
                .border(if (selected) 3.dp else 1.dp, if (selected) app.primary else app.outlineVariant, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text("Aa", style = LagarTheme.type.bodyLegalMd, color = scheme.onSurface, modifier = Modifier.clearAndSetSemantics { })
        }
        Text(stringResource(name), style = LagarTheme.type.labelSm, color = app.onSurfaceVariant)
    }
}
