package app.lagar.ui.search

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDefaults
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.error
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.advanced_date_choose
import app.lagar.resources.date_display
import app.lagar.resources.date_picker_cancel
import app.lagar.resources.date_picker_ok
import app.lagar.resources.ic_expand_more
import app.lagar.resources.months_short
import app.lagar.ui.common.InputFrame
import app.lagar.ui.common.iconColor
import app.lagar.ui.shell.ShellDimens
import kotlinx.datetime.LocalDate
import kotlinx.datetime.TimeZone
import kotlinx.datetime.atStartOfDayIn
import kotlinx.datetime.toLocalDateTime
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringArrayResource
import org.jetbrains.compose.resources.stringResource
import kotlin.time.Instant

/** UTC midnight of [this] in epoch milliseconds, the unit of the M3 date picker. */
internal fun LocalDate.toPickerMillis(): Long = atStartOfDayIn(TimeZone.UTC).toEpochMilliseconds()

/** The date the M3 date picker means by [millis] (UTC midnight). */
internal fun pickerMillisToDate(millis: Long): LocalDate =
    Instant.fromEpochMilliseconds(millis).toLocalDateTime(TimeZone.UTC).date

/** Years the picker offers: the oldest SFS prints are from the 1700s. */
internal val PickerYears = 1700..2100

/** The [months] name (January first) of the month of [date]. */
internal fun monthName(date: LocalDate, months: List<String>): String = months.getOrElse(date.month.ordinal) { date.month.name }

/** [date] in the app language for display: "29 Oct 2026", "29 okt. 2026". */
@Composable
internal fun displayDate(date: LocalDate): String =
    stringResource(Res.string.date_display, date.day, monthName(date, stringArrayResource(Res.array.months_short)), date.year)

/**
 * A date input: [label] above an [InputFrame] showing [value] in the app language (or a prompt), which opens
 * the [LagarDatePickerDialog]. [error] shows under the field and marks it as invalid.
 */
@Composable
internal fun DateField(
    value: LocalDate?,
    onValueChange: (LocalDate) -> Unit,
    label: String,
    error: String?,
    layerKey: LayerKey,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    var picking by rememberSaveable { mutableStateOf(false) }
    val shown = value?.let { displayDate(it) }
    val description = "$label: ${shown ?: stringResource(Res.string.advanced_date_choose)}"
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        Text(
            label,
            style = LagarTheme.type.labelMd,
            color = if (error != null) colors.error else colors.onSurfaceVariant,
            modifier = Modifier.clearAndSetSemantics {},
        )
        InputFrame(
            focused = false,
            isError = error != null,
            modifier = Modifier
                .fillMaxWidth()
                .clip(MaterialTheme.shapes.small)
                .clickable { picking = true }
                .semantics(mergeDescendants = true) {
                    role = Role.Button
                    contentDescription = description
                    if (error != null) error(error)
                },
        ) {
            Text(
                text = shown ?: stringResource(Res.string.advanced_date_choose),
                style = LagarTheme.type.bodyUi,
                color = if (shown != null) colors.onSurface else colors.onSurfaceVariant,
                modifier = Modifier.weight(1f),
            )
            Icon(
                painterResource(Res.drawable.ic_expand_more),
                contentDescription = null,
                tint = LagarTheme.layers.onTint(layerKey),
                modifier = Modifier.size(ShellDimens.SmallIconSize),
            )
        }
        if (error != null) {
            Text(error, style = LagarTheme.type.labelSm, color = colors.error, modifier = Modifier.clearAndSetSemantics {})
        }
    }
    if (picking) {
        LagarDatePickerDialog(
            initial = value,
            layerKey = layerKey,
            onDismiss = { picking = false },
            onConfirm = {
                picking = false
                onValueChange(it)
            },
        )
    }
}

/**
 * The M3 date picker in a dialog, drawn as tier 3 glass (`RadiusTokens.xl`) like the modal sheets. The selected
 * day is filled with the scope's layer `accent`; today, the year selection and the buttons use its AA-safe
 * `onTint`. The picker formats the month and weekdays in the platform locale, which the app sets to its language;
 * its mode toggle lets the date be typed instead.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun LagarDatePickerDialog(
    initial: LocalDate?,
    layerKey: LayerKey,
    onDismiss: () -> Unit,
    onConfirm: (LocalDate) -> Unit,
) {
    val layers = LagarTheme.layers
    val colors = LagarTheme.colors
    val accent = layers.accent(layerKey)
    val onTint = layers.onTint(layerKey)
    val state = rememberDatePickerState(initialSelectedDateMillis = initial?.toPickerMillis(), yearRange = PickerYears)
    val shape = RoundedCornerShape(RadiusTokens.xl)
    val pickerColors = DatePickerDefaults.colors(
        containerColor = Color.Transparent,
        titleContentColor = colors.onSurfaceVariant,
        headlineContentColor = colors.onSurface,
        weekdayContentColor = colors.onSurfaceVariant,
        navigationContentColor = colors.onSurfaceVariant,
        yearContentColor = colors.onSurface,
        currentYearContentColor = onTint,
        selectedYearContentColor = accent.iconColor(),
        selectedYearContainerColor = accent,
        dayContentColor = colors.onSurface,
        selectedDayContentColor = accent.iconColor(),
        selectedDayContainerColor = accent,
        todayContentColor = onTint,
        todayDateBorderColor = accent,
        dividerColor = colors.outlineVariant,
    )
    DatePickerDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.glass(GlassTier.Overlay, hazeState = null, shape = shape),
        shape = shape,
        colors = pickerColors,
        confirmButton = {
            TextButton(
                onClick = { state.selectedDateMillis?.let { onConfirm(pickerMillisToDate(it)) } ?: onDismiss() },
                modifier = Modifier.semantics { role = Role.Button },
            ) { Text(stringResource(Res.string.date_picker_ok), color = onTint, fontWeight = FontWeight.Bold) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(Res.string.date_picker_cancel), color = onTint) }
        },
    ) {
        DatePicker(state = state, colors = pickerColors)
    }
}
