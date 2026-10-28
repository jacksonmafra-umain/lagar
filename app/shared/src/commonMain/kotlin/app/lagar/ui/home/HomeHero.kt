package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_hero_emphasis
import app.lagar.resources.home_hero_subtitle
import app.lagar.resources.home_hero_title
import app.lagar.resources.home_search_example
import app.lagar.resources.home_search_hint
import app.lagar.resources.home_search_submit
import app.lagar.resources.ic_arrow_forward
import app.lagar.resources.ic_search
import app.lagar.ui.common.nameRes
import app.lagar.ui.onboarding.descriptionRes
import app.lagar.ui.onboarding.iconRes
import app.lagar.ui.onboarding.nameRes
import app.lagar.ui.hierarki.iconColor
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Top of the home: scope-tinted backdrop, headline, search field, example hint and advanced-search link. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun HomeHero(
    scope: Scope,
    topInset: Dp,
    onSearch: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val layers = LagarTheme.layers
    val spacing = LagarTheme.spacing
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(layers.tint(scope.key), Color.Transparent)))
            .padding(start = spacing.marginMobile, end = spacing.marginMobile, top = topInset + spacing.md),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        if (scope == Scope.Nationell) {
            val emphasis = stringResource(Res.string.home_hero_emphasis)
            val title = stringResource(Res.string.home_hero_title, emphasis)
            val emphasisColor = layers.onTint(scope.key)
            Text(
                text = remember(title, emphasis, emphasisColor) { emphasised(title, emphasis, emphasisColor) },
                style = LagarTheme.type.headlineSm,
                color = LagarTheme.colors.onSurface,
                textAlign = TextAlign.Center,
            )
            Text(
                text = stringResource(Res.string.home_hero_subtitle),
                style = LagarTheme.type.labelSm,
                color = LagarTheme.colors.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        } else {
            Box(
                modifier = Modifier.size(44.dp).clip(CircleShape).background(layers.accent(scope.key)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(scope.iconRes()), null, tint = layers.accent(scope.key).iconColor(), modifier = Modifier.size(24.dp))
            }
            Text(
                text = stringResource(scope.nameRes()),
                style = LagarTheme.type.headlineSm,
                color = layers.onTint(scope.key),
                textAlign = TextAlign.Center,
            )
            Text(
                text = stringResource(scope.descriptionRes()),
                style = LagarTheme.type.labelSm,
                color = LagarTheme.colors.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        SearchField(scope, onSearch)
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(Res.string.home_search_example),
                style = LagarTheme.type.labelSm,
                color = LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.padding(end = spacing.sm),
            )
            Row(
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .clip(MaterialTheme.shapes.small)
                    .clickable(role = Role.Button, onClick = onOpenAdvancedSearch)
                    .padding(horizontal = spacing.xs),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(spacing.xs),
            ) {
                Icon(painterResource(Res.drawable.ic_search), null, tint = layers.onTint(scope.key), modifier = Modifier.size(16.dp))
                Text(
                    text = stringResource(Res.string.home_advanced_search),
                    style = LagarTheme.type.labelSm,
                    fontWeight = FontWeight.Bold,
                    color = layers.onTint(scope.key),
                )
            }
        }
    }
}

/** The headline with [emphasis] set bold in the scope color; the translator controls where it appears. */
private fun emphasised(title: String, emphasis: String, color: Color) = buildAnnotatedString {
    val start = title.indexOf(emphasis)
    if (start < 0) {
        append(title)
        return@buildAnnotatedString
    }
    append(title.substring(0, start))
    withStyle(SpanStyle(color = color, fontWeight = FontWeight.Bold)) { append(emphasis) }
    append(title.substring(start + emphasis.length))
}

@Composable
private fun SearchField(scope: Scope, onSearch: (String) -> Unit) {
    val layers = LagarTheme.layers
    var query by rememberSaveable { mutableStateOf("") }
    val hint = stringResource(Res.string.home_search_hint)
    val submit = { onSearch(query.trim()) }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = CircleShape,
        color = LagarTheme.colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, layers.accent(scope.key)),
    ) {
        Row(
            modifier = Modifier.heightIn(min = 48.dp).padding(start = LagarTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Icon(painterResource(Res.drawable.ic_search), null, tint = layers.onTint(scope.key), modifier = Modifier.size(24.dp))
            BasicTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.weight(1f).semantics { contentDescription = hint },
                singleLine = true,
                textStyle = LagarTheme.type.bodyUi.copy(color = LagarTheme.colors.onSurface),
                cursorBrush = SolidColor(layers.onTint(scope.key)),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { submit() }),
                decorationBox = { field ->
                    Box(contentAlignment = Alignment.CenterStart) {
                        if (query.isEmpty()) {
                            Text(
                                hint,
                                style = LagarTheme.type.bodyUi,
                                color = LagarTheme.colors.onSurfaceVariant,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        field()
                    }
                },
            )
            val description = stringResource(Res.string.home_search_submit)
            // A 36dp round button inside a 48dp hit area.
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clickable(role = Role.Button, onClick = submit)
                    .semantics { contentDescription = description },
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier.size(36.dp).clip(CircleShape).background(layers.accent(scope.key)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(painterResource(Res.drawable.ic_arrow_forward), null, tint = layers.accent(scope.key).iconColor(), modifier = Modifier.size(20.dp))
                }
            }
        }
    }
}

/** Quick links to the scope's levels that have documents; the first is filled, as in the reference. */
@Composable
internal fun LayerChips(layers: List<DisplayLayer>, onOpenLayer: (DisplayLayer) -> Unit, modifier: Modifier = Modifier) {
    val palette = LagarTheme.layers
    Row(
        modifier = modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        layers.forEachIndexed { index, layer ->
            val accent = palette.accent(layer.key)
            val filled = index == 0
            // A 30dp pill inside a 48dp hit area.
            Box(
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .clip(CircleShape)
                    .clickable(role = Role.Button, onClick = { onOpenLayer(layer) }),
                contentAlignment = Alignment.Center,
            ) {
                Surface(
                    shape = CircleShape,
                    color = if (filled) accent else LagarTheme.colors.surfaceContainerLowest,
                    border = BorderStroke(1.dp, if (filled) accent else palette.border(layer.key)),
                ) {
                    Box(Modifier.heightIn(min = 30.dp).padding(horizontal = LagarTheme.spacing.md), contentAlignment = Alignment.Center) {
                        Text(
                            text = stringResource(layer.nameRes()).uppercase(),
                            style = LagarTheme.type.labelSm,
                            fontWeight = FontWeight.Bold,
                            color = if (filled) accent.iconColor() else palette.onTint(layer.key),
                        )
                    }
                }
            }
        }
    }
}
