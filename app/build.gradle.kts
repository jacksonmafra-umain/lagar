plugins {
    alias(libs.plugins.androidApplication) apply false
    alias(libs.plugins.androidKotlinMultiplatformLibrary) apply false
    alias(libs.plugins.composeMultiplatform) apply false
    alias(libs.plugins.composeCompiler) apply false
    alias(libs.plugins.kotlinMultiplatform) apply false
    alias(libs.plugins.kotlinSerialization) apply false
    alias(libs.plugins.ktlint) apply false
}

// Kotlin style: ktlint over every module; rules and exceptions live in .editorconfig.
val ktlintVersion = libs.versions.ktlint.get()
subprojects {
    apply(plugin = "org.jlleitschuh.gradle.ktlint")
    extensions.configure<org.jlleitschuh.gradle.ktlint.KtlintExtension> {
        version.set(ktlintVersion)
        filter {
            exclude { it.file.path.contains("/build/") }
        }
    }
}
