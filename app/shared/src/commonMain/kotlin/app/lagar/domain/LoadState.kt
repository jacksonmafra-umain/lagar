package app.lagar.domain

sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>

    data class Loaded<T>(val value: T) : LoadState<T>

    data class Failed(val retry: () -> Unit) : LoadState<Nothing>
}
