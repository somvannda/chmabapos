package com.chmaba.pos.data.plans

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

/**
 * Guards the client-side billing table against drifting from the web.
 *
 * Source of truth: apps/web/src/features/marketing.jsx (BILLING_CYCLES) and the
 * price helpers beside it. If these values change, both products must change
 * together or the two clients will quote different prices for the same plan.
 */
class BillingCycleParityTest {

    @Test
    fun cyclesMatchWebMarketingJsx() {
        assertEquals(3, BillingCycle.entries.size)

        BillingCycle.Monthly.let { cycle ->
            assertEquals("monthly", cycle.key)
            assertEquals("Monthly", cycle.label)
            assertEquals(1, cycle.multiplier)
            assertEquals(0.0, cycle.discount, 0.0001)
            assertNull(cycle.badge)
            assertEquals("billed monthly", cycle.billedLabel)
        }

        BillingCycle.SemiAnnual.let { cycle ->
            assertEquals("semi_annual", cycle.key)
            assertEquals("Semi-annual", cycle.label)
            assertEquals(6, cycle.multiplier)
            assertEquals(0.15, cycle.discount, 0.0001)
            assertEquals("Save 15%", cycle.badge)
            assertEquals("billed every 6 months", cycle.billedLabel)
        }

        BillingCycle.Annual.let { cycle ->
            assertEquals("annual", cycle.key)
            assertEquals("Annual", cycle.label)
            assertEquals(12, cycle.multiplier)
            assertEquals(0.20, cycle.discount, 0.0001)
            assertEquals("Save 20%", cycle.badge)
            assertEquals("billed annually", cycle.billedLabel)
        }
    }

    @Test
    fun priceMathMatchesWeb() {
        val starter = PlanDto(code = "starter", name = "Starter", monthlyPrice = "19.00")

        assertEquals("$19.00", starter.priceLabel(BillingCycle.Monthly))
        assertEquals("$16.15", starter.priceLabel(BillingCycle.SemiAnnual))
        assertEquals("$15.20", starter.priceLabel(BillingCycle.Annual))

        assertEquals("19.00", starter.totalFor(BillingCycle.Monthly))
        assertEquals("96.90", starter.totalFor(BillingCycle.SemiAnnual))
        assertEquals("182.40", starter.totalFor(BillingCycle.Annual))
    }

    @Test
    fun freePlanShowsZeroAndNoTotal() {
        val free = PlanDto(code = "free", name = "Free", monthlyPrice = "0.00")
        assertTrue(free.isFree())
        assertEquals("$0", free.priceLabel(BillingCycle.Annual))
        assertNull(free.totalFor(BillingCycle.Annual))
    }

    @Test
    fun missingPriceIsTreatedAsFree() {
        val blank = PlanDto(code = "x", name = "X", monthlyPrice = null)
        assertTrue(blank.isFree())
        assertNull(blank.totalFor(BillingCycle.Monthly))
    }

    @Test
    fun featuredIsStarterElseFirstPaid() {
        val free = PlanDto(code = "free", monthlyPrice = "0.00")
        val starter = PlanDto(code = "starter", monthlyPrice = "19.00")
        val pro = PlanDto(code = "pro", monthlyPrice = "49.00")

        assertEquals("starter", listOf(free, starter, pro).featuredCode())
        assertEquals("pro", listOf(free, pro).featuredCode())
        assertNull(listOf(free).featuredCode())
    }

    /** A comma-decimal locale must not leak into a price shown to a cashier. */
    @Test
    fun priceAlwaysUsesDotDecimal() {
        val original = Locale.getDefault()
        try {
            Locale.setDefault(Locale.FRANCE)
            val starter = PlanDto(monthlyPrice = "19.00")
            assertEquals("$16.15", starter.priceLabel(BillingCycle.SemiAnnual))
            assertEquals("96.90", starter.totalFor(BillingCycle.SemiAnnual))
        } finally {
            Locale.setDefault(original)
        }
    }
}
