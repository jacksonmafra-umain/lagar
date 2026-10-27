plugins {
    `kotlin-dsl`
}

dependencies {
    implementation(libs.snakeyaml)
    testImplementation(kotlin("test"))
}

gradlePlugin {
    plugins {
        register("designTokens") {
            id = "app.lagar.design-tokens"
            implementationClass = "app.lagar.tokens.DesignTokensPlugin"
        }
    }
}

tasks.test {
    useJUnitPlatform()
}
