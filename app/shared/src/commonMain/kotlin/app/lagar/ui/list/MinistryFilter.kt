package app.lagar.ui.list

/** Narrows a layer list to one issuing ministry: [id] from the per-ministry index, [name] for the header. */
data class MinistryFilter(val id: String, val name: String)

/** Narrows a region or municipality list to one län or kommun: [code] from the per-locality index, [name] for the header. */
data class LocalityFilter(val code: String, val name: String)
