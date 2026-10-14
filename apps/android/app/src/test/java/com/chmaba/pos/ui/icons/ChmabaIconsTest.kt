package com.chmaba.pos.ui.icons

import androidx.compose.ui.graphics.vector.ImageVector
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Safety net for the hand-written Lucide path data in [ChmabaIcons].
 *
 * The icons are built from raw SVG path strings via `addPathNodes`. Malformed
 * data does not fail the compiler — it throws when the object initialises, which
 * on a device means a crash at app start. Touching every property here turns
 * that into a test failure instead.
 */
class ChmabaIconsTest {

    private val iconFields = ChmabaIcons::class.java.declaredFields
        .filter { ImageVector::class.java.isAssignableFrom(it.type) }
        .onEach { it.isAccessible = true }

    @Test
    fun exposesAMeaningfulIconSet() {
        assertTrue(
            "expected at least 40 icons, found ${iconFields.size}",
            iconFields.size >= 40,
        )
    }

    @Test
    fun everyIconBuildsWithUsableGeometry() {
        iconFields.forEach { field ->
            val vector = field.get(ChmabaIcons) as ImageVector
            val name = field.name

            assertTrue("$name: missing default width", vector.defaultWidth.value > 0f)
            assertTrue("$name: missing default height", vector.defaultHeight.value > 0f)
            assertTrue("$name: missing viewport width", vector.viewportWidth > 0f)
            assertTrue("$name: missing viewport height", vector.viewportHeight > 0f)
            assertTrue("$name: no path nodes were produced", vector.root.size > 0)
        }
    }

    @Test
    fun iconsAreUniquelyNamed() {
        val names = iconFields.map { it.name }
        assertTrue("duplicate icon property names: $names", names.size == names.toSet().size)
    }
}
