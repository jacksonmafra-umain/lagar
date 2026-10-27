package app.lagar.tokens

import org.gradle.api.Plugin
import org.gradle.api.Project

/**
 * Registers `generateDesignTokens`, which turns the repository's DESIGN.md into Kotlin sources.
 * The consuming build adds the task's `outputDir` to its common source set.
 */
class DesignTokensPlugin : Plugin<Project> {
    override fun apply(project: Project) {
        project.tasks.register("generateDesignTokens", GenerateDesignTokensTask::class.java) {
            // The Gradle root is `app/`; DESIGN.md lives at the repository root.
            designFile.set(project.rootProject.layout.projectDirectory.file("../DESIGN.md"))
            outputDir.set(project.layout.buildDirectory.dir("generated/designTokens/commonMain/kotlin"))
        }
    }
}
