package app.lagar.domain

import app.lagar.data.ApiIndex
import app.lagar.data.ListingItem
import app.lagar.designsystem.generated.LayerKey

/** The geographic level the user reads law at; [key] colors it and [layers] are the levels it covers. */
enum class Scope(val key: LayerKey, val layers: List<DisplayLayer>) {
    Nationell(
        LayerKey.SfsAct,
        listOf(
            DisplayLayer.Fundamental,
            DisplayLayer.SfsAct,
            DisplayLayer.SfsOrdinance,
            DisplayLayer.Agency,
            DisplayLayer.CaseLaw,
            DisplayLayer.Eu,
        ),
    ),
    Region(LayerKey.Region, listOf(DisplayLayer.Region)),
    Kommun(LayerKey.Municipality, listOf(DisplayLayer.Municipality)),
}

/** Documents across the levels of [scope]. */
fun ApiIndex.count(scope: Scope): Int = scope.layers.sumOf { count(it) }

/** The level whose documents belong to one län (Region) or kommun (Kommun); null for Nationell. */
val Scope.localityLayer: DisplayLayer?
    get() = when (this) {
        Scope.Nationell -> null
        Scope.Region -> DisplayLayer.Region
        Scope.Kommun -> DisplayLayer.Municipality
    }

/** The code of [locality] this scope reads: the län for Region, the kommun for Kommun; null for Nationell or when unset. */
fun Scope.localityCode(locality: Locality): String? = when (this) {
    Scope.Nationell -> null
    Scope.Region -> locality.regionCode
    Scope.Kommun -> locality.kommunCode
}

/**
 * Whether a document of this scope's levels also belongs to the chosen [locality]: always for Nationell; for
 * Region and Kommun its county or kommun code must equal the chosen one, so nothing matches while none is chosen.
 */
fun Scope.coversLocality(item: ListingItem, locality: Locality): Boolean = when (this) {
    Scope.Nationell -> true
    Scope.Region -> locality.regionCode != null && item.regionCode == locality.regionCode
    Scope.Kommun -> locality.kommunCode != null && item.municipalityCode == locality.kommunCode
}
