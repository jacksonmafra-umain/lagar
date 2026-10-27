package app.lagar.data

data class DataSourceConfig(
    val useSample: Boolean = true,
    val baseUrl: String = "http://localhost:8000/api/v1/",
)
