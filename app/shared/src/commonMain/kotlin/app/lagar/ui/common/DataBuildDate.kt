package app.lagar.ui.common

import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.produceState
import app.lagar.data.LagarRepository
import org.koin.compose.koinInject
import kotlin.coroutines.cancellation.CancellationException

/** ISO date (`yyyy-MM-dd`) of the data build; stays null while loading and when the index cannot be loaded. */
@Composable
fun rememberDataBuildDate(): State<String?> {
    val repository = koinInject<LagarRepository>()
    return produceState<String?>(initialValue = null, repository) {
        value = try {
            repository.index().builtAt.take(10)
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
    }
}
