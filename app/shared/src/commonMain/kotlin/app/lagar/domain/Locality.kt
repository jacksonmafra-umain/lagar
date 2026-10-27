package app.lagar.domain

import kotlinx.serialization.Serializable

@Serializable
data class Region(val code: String, val name: String)

@Serializable
data class Kommun(val code: String, val name: String, val regionCode: String)

/** The user's chosen län and kommun; either may be unset. */
data class Locality(val regionCode: String?, val kommunCode: String?)
