package app.lagar.domain

import app.lagar.data.ApiIndex
import app.lagar.designsystem.generated.LayerKey

/** The nine levels shown in the app; SFS is split into acts and ordinances. */
enum class DisplayLayer(val apiLayer: String, val apiType: String?, val key: LayerKey) {
    Fundamental("fundamental", null, LayerKey.Fundamental),
    SfsAct("sfs", "act", LayerKey.SfsAct),
    SfsOrdinance("sfs", "ordinance", LayerKey.SfsOrdinance),
    Agency("agency", null, LayerKey.Agency),
    CaseLaw("case_law", null, LayerKey.CaseLaw),
    Eu("eu", null, LayerKey.Eu),
    Region("region", null, LayerKey.Region),
    Municipality("municipality", null, LayerKey.Municipality),
    Service("service", null, LayerKey.Service);

    companion object {
        /** The level a `LayerList(layer, type)` route shows; untyped levels ignore [type]. */
        fun fromRoute(layer: String, type: String?): DisplayLayer? =
            entries.firstOrNull { it.apiLayer == layer && (it.apiType == null || it.apiType == type) }
    }
}

/** Documents at this level: the series count for typed levels, the layer count otherwise; 0 when absent. */
fun ApiIndex.count(d: DisplayLayer): Int {
    val layer = layers.firstOrNull { it.id == d.apiLayer } ?: return 0
    val type = d.apiType ?: return layer.count
    return layer.series.firstOrNull { it.id == type }?.count ?: 0
}
