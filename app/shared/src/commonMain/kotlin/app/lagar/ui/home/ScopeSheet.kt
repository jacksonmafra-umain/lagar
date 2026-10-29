package app.lagar.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import app.lagar.data.LagarRepository
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.domain.Scope
import app.lagar.domain.count
import app.lagar.domain.withRegion
import app.lagar.resources.Res
import app.lagar.resources.onboarding_done
import app.lagar.resources.scope_sheet_locality
import app.lagar.resources.scope_sheet_title
import app.lagar.settings.UserPreferences
import app.lagar.ui.common.LagarButton
import app.lagar.ui.common.SheetShape
import app.lagar.ui.common.sheetGlass
import app.lagar.ui.onboarding.LocalityPickers
import app.lagar.ui.onboarding.ScopeCard
import kotlinx.coroutines.CancellationException
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/**
 * Switches the scope and the locality. Edits a local draft: "Klar" writes it to [UserPreferences] and
 * closes, dismissing the sheet discards it. Home collects the preference flows, so it reloads by itself.
 * [initialScope] preselects a scope in the draft (the drawer opens the sheet this way to pick its locality).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScopeSheet(onDismiss: () -> Unit, initialScope: Scope? = null) {
    val preferences = koinInject<UserPreferences>()
    val repository = koinInject<LagarRepository>()
    val activeScope by preferences.scope.collectAsState()
    var draftScope by remember { mutableStateOf(initialScope ?: preferences.scope.value) }
    var draftLocality by remember { mutableStateOf(preferences.locality.value) }
    // Counts are decoration: a failed index load just hides the badges.
    val counts by produceState<Map<Scope, Int>?>(null) {
        value = try {
            val index = repository.index()
            Scope.entries.associateWith { index.count(it) }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
    }
    val spacing = LagarTheme.spacing
    val shape = SheetShape

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        modifier = Modifier.sheetGlass(shape),
        shape = shape,
        containerColor = Color.Transparent,
        contentColor = LagarTheme.colors.onSurface,
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier
                    .weight(1f, fill = false)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = spacing.marginMobile)
                    .padding(top = spacing.lg),
                verticalArrangement = Arrangement.spacedBy(spacing.md),
            ) {
                Text(stringResource(Res.string.scope_sheet_title), style = LagarTheme.type.headlineMd, color = LagarTheme.colors.onSurface)
                Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    Scope.entries.forEach { scope ->
                        ScopeCard(
                            scope = scope,
                            count = counts?.get(scope),
                            selected = draftScope == scope,
                            onClick = { draftScope = scope },
                            active = activeScope == scope,
                        )
                    }
                }
                Text(stringResource(Res.string.scope_sheet_locality), style = LagarTheme.type.headlineSm, color = LagarTheme.colors.onSurface)
                LocalityPickers(
                    locality = draftLocality,
                    onRegion = { draftLocality = draftLocality.withRegion(it) },
                    onKommun = { draftLocality = draftLocality.copy(kommunCode = it) },
                )
            }
            LagarButton(
                onClick = {
                    preferences.setScope(draftScope)
                    preferences.setLocality(draftLocality)
                    onDismiss()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .imePadding()
                    .padding(horizontal = spacing.marginMobile, vertical = spacing.md),
            ) { Text(stringResource(Res.string.onboarding_done)) }
        }
    }
}
