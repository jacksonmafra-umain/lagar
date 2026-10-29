package app.lagar.settings

/** The user's reduce-transparency setting: follow the platform, or force glass surfaces opaque or translucent. */
enum class ReduceTransparency {
    System,
    On,
    Off,
    ;

    /** Whether glass surfaces draw their opaque fallback; [systemEnabled] is the platform's own setting. */
    fun resolve(systemEnabled: Boolean): Boolean = when (this) {
        System -> systemEnabled
        On -> true
        Off -> false
    }
}
