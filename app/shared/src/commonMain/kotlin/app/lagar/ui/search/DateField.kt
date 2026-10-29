package app.lagar.ui.search

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import app.lagar.resources.Res
import app.lagar.resources.advanced_date_placeholder
import app.lagar.ui.common.LagarTextField
import org.jetbrains.compose.resources.stringResource

/** Text input for a `yyyy-mm-dd` date; shows [error] under the field when not null. */
@Composable
internal fun DateField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    error: String?,
    modifier: Modifier = Modifier,
) {
    LagarTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        label = label,
        placeholder = stringResource(Res.string.advanced_date_placeholder),
        error = error,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
    )
}
