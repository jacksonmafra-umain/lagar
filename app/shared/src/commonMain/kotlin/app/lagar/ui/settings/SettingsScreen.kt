package app.lagar.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import app.lagar.designsystem.LagarTheme
import app.lagar.i18n.LanguageChoice
import app.lagar.resources.Res
import app.lagar.resources.about_credits
import app.lagar.resources.about_license
import app.lagar.resources.drawer_about
import app.lagar.resources.drawer_data_built
import app.lagar.resources.language_english
import app.lagar.resources.language_swedish
import app.lagar.resources.settings_language
import app.lagar.resources.settings_system
import app.lagar.resources.settings_theme
import app.lagar.resources.settings_title
import app.lagar.resources.theme_dark
import app.lagar.resources.theme_light
import app.lagar.settings.ThemeMode
import app.lagar.settings.UserPreferences
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.common.rememberDataBuildDate
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/** Language, theme and about. Choices apply immediately and are stored on the device. */
@Composable
fun SettingsRoute(onBack: () -> Unit) {
    val preferences = koinInject<UserPreferences>()
    val language by preferences.language.collectAsState()
    val theme by preferences.theme.collectAsState()
    val builtAt by rememberDataBuildDate()
    SettingsScreen(
        language = language,
        theme = theme,
        builtAt = builtAt,
        onLanguage = preferences::setLanguage,
        onTheme = preferences::setTheme,
        onBack = onBack,
    )
}

@Composable
fun SettingsScreen(
    language: LanguageChoice,
    theme: ThemeMode,
    builtAt: String?,
    onLanguage: (LanguageChoice) -> Unit,
    onTheme: (ThemeMode) -> Unit,
    onBack: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val colors = LagarTheme.colors
    val hazeState = remember { HazeState() }
    var barHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    Box(Modifier.fillMaxSize().background(colors.surface)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .hazeSource(hazeState)
                .verticalScroll(rememberScrollState())
                .padding(PaddingValues(top = barHeight + spacing.md, bottom = bottomInset + spacing.lg))
                .padding(horizontal = spacing.marginMobile),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            val system = stringResource(Res.string.settings_system)
            OptionGroup(
                title = stringResource(Res.string.settings_language),
                options = listOf(
                    LanguageChoice.System to system,
                    LanguageChoice.Swedish to stringResource(Res.string.language_swedish),
                    LanguageChoice.English to stringResource(Res.string.language_english),
                ),
                selected = language,
                onSelect = onLanguage,
            )
            OptionGroup(
                title = stringResource(Res.string.settings_theme),
                options = listOf(
                    ThemeMode.System to system,
                    ThemeMode.Light to stringResource(Res.string.theme_light),
                    ThemeMode.Dark to stringResource(Res.string.theme_dark),
                ),
                selected = theme,
                onSelect = onTheme,
            )
            Column(verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                SectionTitle(stringResource(Res.string.drawer_about))
                AboutLine(stringResource(Res.string.about_credits, CREDITS_NAME))
                AboutLine(stringResource(Res.string.about_license, LICENSE_NAME))
                builtAt?.let { AboutLine(stringResource(Res.string.drawer_data_built, it)) }
            }
        }
        BackTopBar(hazeState, onBack, onHeightChange = { barHeight = it }, modifier = Modifier.align(Alignment.TopCenter)) {
            Text(
                text = stringResource(Res.string.settings_title),
                style = LagarTheme.type.headlineSm,
                color = colors.onSurface,
                modifier = Modifier.semantics { heading() },
            )
        }
    }
}

// Proper names, identical in every language.
private const val CREDITS_NAME = "Jackson F. de A. Mafra"
private const val LICENSE_NAME = "MIT"

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = LagarTheme.type.labelMd,
        color = LagarTheme.colors.onSurfaceVariant,
        modifier = Modifier.semantics { heading() },
    )
}

@Composable
private fun AboutLine(text: String) {
    Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface)
}

@Composable
private fun <T> OptionGroup(title: String, options: List<Pair<T, String>>, selected: T, onSelect: (T) -> Unit) {
    Column {
        SectionTitle(title)
        Column(Modifier.selectableGroup()) {
            options.forEach { (value, label) ->
                OptionRow(label = label, selected = value == selected, onClick = { onSelect(value) })
            }
        }
    }
}

@Composable
private fun OptionRow(label: String, selected: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = ShellDimens.TouchTarget)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(
            selected = selected,
            onClick = null,
            colors = RadioButtonDefaults.colors(selectedColor = colors.primary, unselectedColor = colors.onSurfaceVariant),
        )
        Text(
            text = label,
            style = LagarTheme.type.bodyUi,
            color = colors.onSurface,
            modifier = Modifier.padding(start = LagarTheme.spacing.sm),
        )
    }
}
