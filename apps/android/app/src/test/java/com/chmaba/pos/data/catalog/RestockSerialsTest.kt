package com.chmaba.pos.data.catalog

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The rule that decides whether a serial-tracked receipt can be sent at all.
 *
 * The API refuses a serial-tracked restock without one serial per unit, so getting this wrong means
 * a round trip that fails and a cashier who has already put the delivery note down.
 */
class RestockSerialsTest {

    @Test
    fun commasAndNewlinesBothSeparate() {
        assertEquals(listOf("SN-1", "SN-2", "SN-3"), parseSerialNumbers("SN-1, SN-2\nSN-3"))
    }

    @Test
    fun aTrailingSeparatorIsNotAnEmptySerial() {
        assertEquals(listOf("SN-1"), parseSerialNumbers("SN-1,"))
    }

    @Test
    fun blankTextClaimsNothing() {
        assertNull(parseSerialNumbers("  \n , \n "))
    }

    @Test
    fun oneSerialPerUnitIsAccepted() {
        assertNull(serialProblem(2, "SN-1\nSN-2"))
    }

    @Test
    fun tooFewAreCounted() {
        assertEquals("That is 1 serial number for 3 units.", serialProblem(3, "SN-1"))
    }

    @Test
    fun tooManyAreCounted() {
        assertEquals("That is 3 serial numbers for 1 unit.", serialProblem(1, "SN-1,SN-2,SN-3"))
    }

    @Test
    fun noneSaysWhatIsNeeded() {
        assertEquals("Enter one serial number per unit - 2 in all.", serialProblem(2, ""))
    }

    @Test
    fun anUnreadableQuantityIsLeftToTheQuantityField() {
        assertNull(serialProblem(null, ""))
    }
}
