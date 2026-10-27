package app.lagar.i18n

/** Languages the app ships resources for. Adding one means a `values-xx` folder plus an entry here. */
enum class SupportedLanguage(val tag: String) {
    Swedish("sv"),
    English("en"),
    ;

    companion object {
        /** Matches the language part of [systemTag] (`en-GB`, `sv_SE`); anything else is Swedish. */
        fun resolve(systemTag: String): SupportedLanguage {
            val language = systemTag.substringBefore('-').substringBefore('_').lowercase()
            return entries.firstOrNull { it.tag == language } ?: Swedish
        }
    }
}

/** The user's language setting: follow the system or force one language. */
enum class LanguageChoice {
    System,
    Swedish,
    English,
    ;

    fun resolve(systemTag: String): SupportedLanguage = when (this) {
        System -> SupportedLanguage.resolve(systemTag)
        Swedish -> SupportedLanguage.Swedish
        English -> SupportedLanguage.English
    }
}
