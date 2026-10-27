package app.lagar.domain

import app.lagar.data.ApiIndex
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
