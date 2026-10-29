package app.lagar.i18n

import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import app.lagar.resources.Res
import app.lagar.resources.document_count
import org.jetbrains.compose.resources.pluralStringResource

/** The language the app shows, set by [ProvideAppLocale]; Swedish outside it. */
val LocalAppLanguage = staticCompositionLocalOf { SupportedLanguage.Swedish }

/** Separator between groups of three digits: a no-break space in Swedish ("26 813"), a comma in English ("26,813"). */
val SupportedLanguage.groupSeparator: Char
    get() = when (this) {
        SupportedLanguage.Swedish -> ' '
        SupportedLanguage.English -> ','
    }

/** [count] with its digits grouped in threes for this language; the same on every platform. */
fun SupportedLanguage.formatCount(count: Long): String {
    val digits = if (count < 0) count.toString().drop(1) else count.toString()
    val grouped = digits.reversed().chunked(3).joinToString(groupSeparator.toString()).reversed()
    return if (count < 0) "-$grouped" else grouped
}

fun SupportedLanguage.formatCount(count: Int): String = formatCount(count.toLong())

/** [count] digit-grouped for the app language. */
@Composable
@ReadOnlyComposable
fun formatCount(count: Int): String = LocalAppLanguage.current.formatCount(count)

/** "26 813 dokument" / "26,813 documents": the document count plural with a digit-grouped number. */
@Composable
fun documentCount(count: Int): String = pluralStringResource(Res.plurals.document_count, count, formatCount(count))
