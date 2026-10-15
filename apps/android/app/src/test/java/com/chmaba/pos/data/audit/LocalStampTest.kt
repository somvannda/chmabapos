package com.chmaba.pos.data.audit

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.ZoneId

/**
 * How a recorded instant is shown.
 *
 * The API sends an offset ("+00:00"), so the tempting fix - slicing characters out of the string -
 * would display UTC to everyone. These pin the conversion, including the zone this store's team
 * actually reads in.
 */
class LocalStampTest {

    private val instant = "2026-10-15T04:35:37.652927+00:00"

    @Test
    fun anInstantIsRenderedInTheZoneAskedFor() {
        assertEquals("15 Oct 2026, 04:35", localStamp(instant, ZoneId.of("UTC")))
        assertEquals("15 Oct 2026, 11:35", localStamp(instant, ZoneId.of("Asia/Phnom_Penh")))
        assertEquals("15 Oct 2026, 06:35", localStamp(instant, ZoneId.of("Europe/Berlin")))
    }

    @Test
    fun anUnparseableValueIsLeftAloneRatherThanGuessed() {
        assertEquals("whenever", localStamp("whenever", ZoneId.of("UTC")))
        assertEquals("", localStamp(null, ZoneId.of("UTC")))
        assertEquals("", localStamp("", ZoneId.of("UTC")))
    }
}
