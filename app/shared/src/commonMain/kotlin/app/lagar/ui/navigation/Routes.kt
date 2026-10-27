package app.lagar.ui.navigation

import kotlinx.serialization.Serializable

@Serializable data object Utforska
@Serializable data object Hierarki
@Serializable data object Sparade
@Serializable data object Tjanster
@Serializable data class LayerList(val layer: String, val type: String? = null)
@Serializable data class Reader(val id: String)
@Serializable data object Settings
