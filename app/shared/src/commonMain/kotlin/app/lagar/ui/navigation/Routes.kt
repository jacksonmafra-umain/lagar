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

/** A layer's documents; with [ministry] (an id from the per-ministry index) only that ministry's, under [ministryName]. */
@Serializable
data class LayerList(
    val layer: String,
    val type: String? = null,
    val ministry: String? = null,
    val ministryName: String? = null,
)

/** The issuing ministries of one SFS series, from the per-ministry index. */
@Serializable data class Ministries(val layer: String, val type: String)

/** A document; [anchor] (an outline anchor such as `k3p1`) is scrolled to once the text has loaded. */
@Serializable data class Reader(val id: String, val anchor: String? = null)

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
    val inForceFrom: String? = null,
    val inForceTo: String? = null,
    val vacatioLegis: Boolean = false,
    val sort: String? = null,
)

@Serializable data object AdvancedSearch
