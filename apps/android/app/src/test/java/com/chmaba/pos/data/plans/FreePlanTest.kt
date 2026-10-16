package com.chmaba.pos.data.plans

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Which page the billing screen opens on.
 *
 * A free workspace gets the upgrade page and a paying one gets the list with its plan marked, so
 * this rule decides what a merchant sees about money. It answers false whenever it is not sure:
 * showing a paying workspace the upgrade page would be the worse of the two mistakes, and a null
 * plan code is exactly the state a workspace is in before the subscription has been read.
 */
class FreePlanTest {

    private val catalogue = listOf(
        PlanDto(code = "free", name = "Free", monthlyPrice = "0.00"),
        PlanDto(code = "starter", name = "Starter", monthlyPrice = "19.00"),
        PlanDto(code = "pro", name = "Pro", monthlyPrice = "49.00"),
    )

    @Test
    fun aWorkspaceOnTheCataloguesFreePlanGetsTheUpgradePage() {
        assertTrue(catalogue.isOnFreePlan("free"))
    }

    @Test
    fun aPayingWorkspaceGetsTheList() {
        assertFalse(catalogue.isOnFreePlan("starter"))
        assertFalse(catalogue.isOnFreePlan("pro"))
    }

    @Test
    fun anUnknownPlanIsNotTreatedAsFree() {
        // Before the subscription is read, or if the catalogue prices everything.
        assertFalse(catalogue.isOnFreePlan(null))
        assertFalse(catalogue.isOnFreePlan(""))
        assertFalse(catalogue.isOnFreePlan("something_else"))
        assertFalse(emptyList<PlanDto>().isOnFreePlan("free"))
    }
}
