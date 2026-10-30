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
    Service("service", null, LayerKey.Service),
    ;

    /** Whether the API has a per-ministry index for this level (`<layer>/<type>/by-ministry/`): the SFS series. */
    val hasMinistryIndex: Boolean get() = apiLayer == "sfs" && apiType != null

    /**
     * Other API types counted at this level besides [apiType]: SFS other statutes are shown under the SFS acts
     * colour group (docs/api.md), so the totals, the distribution and the scope counts include them.
     */
    val groupedTypes: List<String> get() = if (this == SfsAct) listOf(OTHER_STATUTE) else emptyList()

    companion object {
        /** The level a `LayerList(layer, type)` route shows; untyped levels ignore [type]. */
        fun fromRoute(layer: String, type: String?): DisplayLayer? =
            entries.firstOrNull { it.apiLayer == layer && (it.apiType == null || it.apiType == type) }

        /** The level of a document of API `type`; null for `other_statute`, `treaty` (both national) and unknown types. */
        fun forType(type: String): DisplayLayer? = when (type) {
            "fundamental_law" -> Fundamental
            "act" -> SfsAct
            "ordinance" -> SfsOrdinance
            "agency_regulation" -> Agency
            "case_report", "case_notice" -> CaseLaw
            "eu_regulation", "eu_directive", "eu_decision", "eu_judgment" -> Eu
            "county_regulation" -> Region
            "municipal_regulation" -> Municipality
            else -> null
        }
    }
}

/** API type of the SFS statutes that are neither acts nor ordinances. */
const val OTHER_STATUTE = "other_statute"

/**
 * Documents at this level: the layer count for untyped levels, otherwise the count of the level's series plus
 * its [DisplayLayer.groupedTypes] (SFS acts include the other statutes); 0 when absent.
 */
fun ApiIndex.count(d: DisplayLayer): Int {
    val layer = layers.firstOrNull { it.id == d.apiLayer } ?: return 0
    val type = d.apiType ?: return layer.count
    return (listOf(type) + d.groupedTypes).sumOf { id -> layer.series.firstOrNull { it.id == id }?.count ?: 0 }
}

/** The SFS other statutes, counted within [DisplayLayer.SfsAct]; 0 when absent. */
fun ApiIndex.otherStatuteCount(): Int =
    layers.firstOrNull { it.id == DisplayLayer.SfsAct.apiLayer }?.series?.firstOrNull { it.id == OTHER_STATUTE }?.count ?: 0
