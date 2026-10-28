package app.lagar.ui.navigation

import kotlinx.serialization.Serializable

@Serializable data object Splash
@Serializable data object OnboardingWelcome
@Serializable data object OnboardingScope
@Serializable data object OnboardingLocality
@Serializable data object Utforska
@Serializable data object Hierarki
@Serializable data object Sparade
@Serializable data object Tjanster
@Serializable data class LayerList(val layer: String, val type: String? = null)
@Serializable data class Reader(val id: String)
@Serializable data object Settings

/**
 * Search results. The filters of the advanced search travel as optional params (types comma-separated,
 * dates ISO), so the query survives process death.
 */
@Serializable
data class Search(
    val text: String = "",
    val types: String? = null,
    val from: String? = null,
    val to: String? = null,
    val mode: String? = null,
    val status: String? = null,
)

@Serializable data object AdvancedSearch
