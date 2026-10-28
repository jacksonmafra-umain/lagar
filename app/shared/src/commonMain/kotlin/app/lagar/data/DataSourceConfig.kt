package app.lagar.data

data class DataSourceConfig(
    val useSample: Boolean = true,
    val baseUrl: String = "http://localhost:8000/api/v1/",
) {
    companion object {
        /** The static API published to GitHub Pages from `main`. */
        const val PUBLISHED_API = "https://jacksonmafra-umain.github.io/lagar/api/v1/"
    }
}
