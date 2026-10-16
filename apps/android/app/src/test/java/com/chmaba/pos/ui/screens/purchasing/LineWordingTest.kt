package com.chmaba.pos.ui.screens.purchasing

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * How a purchase order's line count is worded.
 *
 * The row appended " lines" whatever the number, so every order raised by the app's own form - which
 * has exactly one line - read "1 lines".
 */
class LineWordingTest {

    @Test
    fun oneLineIsSingular() {
        assertEquals("1 line", lineWording(1))
    }

    @Test
    fun moreThanOneIsPlural() {
        assertEquals("2 lines", lineWording(2))
        assertEquals("17 lines", lineWording(17))
    }

    @Test
    fun noneIsStillAWord() {
        // The payload carries a line snapshot list, so this is only reachable if the server ever
        // records an order with no lines - which it refuses to create. It should still read.
        assertEquals("0 lines", lineWording(0))
    }
}
