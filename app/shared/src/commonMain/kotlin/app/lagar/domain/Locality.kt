package app.lagar.domain

import kotlinx.serialization.Serializable

@Serializable
data class Region(val code: String, val name: String)

@Serializable
data class Kommun(val code: String, val name: String, val regionCode: String)

/** The user's chosen län and kommun; either may be unset. */
data class Locality(val regionCode: String?, val kommunCode: String?)

/** Picking a different län clears the kommun, since it belongs to the previous one. */
fun Locality.withRegion(code: String?): Locality = Locality(code, if (code == regionCode) kommunCode else null)

/** Whether [locality] holds what [this] scope needs: nothing for Nationell, a län for Region, a kommun for Kommun. */
fun Scope.hasLocality(locality: Locality): Boolean = when (this) {
    Scope.Nationell -> true
    Scope.Region -> locality.regionCode != null
    Scope.Kommun -> locality.regionCode != null && locality.kommunCode != null
}
