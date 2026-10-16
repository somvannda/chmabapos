package com.chmaba.pos.ui.screens.pos

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * How a tap on a modifier behaves, which is the rule the sheet uses (README: "only `is_required` is
 * honoured" - it was worse than that: `max_select` was dropped, so every group was single-choice).
 */
class ModifierSelectionTest {

    private val extra = ModifierOption(id = "hot", name = "Extra hot", priceDelta = 0.5)
    private val soy = ModifierOption(id = "soy", name = "Soy", priceDelta = 0.75)
    private val oat = ModifierOption(id = "oat", name = "Oat", priceDelta = 0.75)

    private fun group(max: Int, required: Boolean = false) =
        ModifierGroup(name = "Milk", options = listOf(soy, oat), required = required, maxSelect = max)

    private fun pick(option: ModifierOption) = SelectedModifier(option.id, option.name, option.priceDelta)

    @Test
    fun aSingleChoiceGroupSwapsRatherThanAccumulating() {
        val milk = group(max = 1)

        val first = toggledSelection(emptyList(), milk, soy)
        assertEquals(listOf("soy"), first.map { it.optionId })

        val second = toggledSelection(first, milk, oat)
        assertEquals(listOf("oat"), second.map { it.optionId })
    }

    @Test
    fun aGroupWithRoomHoldsMoreThanOne() {
        val toppings = ModifierGroup(name = "Toppings", options = listOf(extra, soy, oat), maxSelect = 3)

        var chosen = toggledSelection(emptyList(), toppings, extra)
        chosen = toggledSelection(chosen, toppings, soy)
        chosen = toggledSelection(chosen, toppings, oat)

        assertEquals(listOf("hot", "soy", "oat"), chosen.map { it.optionId })
    }

    @Test
    fun theCapIsRespected() {
        val two = ModifierGroup(name = "Two only", options = listOf(extra, soy, oat), maxSelect = 2)

        var chosen = toggledSelection(emptyList(), two, extra)
        chosen = toggledSelection(chosen, two, soy)
        val refused = toggledSelection(chosen, two, oat)

        assertEquals(listOf("hot", "soy"), refused.map { it.optionId })
    }

    @Test
    fun tappingAChosenOptionTakesItOff() {
        val toppings = ModifierGroup(name = "Toppings", options = listOf(extra, soy), maxSelect = 2)

        var chosen = toggledSelection(emptyList(), toppings, extra)
        chosen = toggledSelection(chosen, toppings, soy)
        chosen = toggledSelection(chosen, toppings, extra)

        assertEquals(listOf("soy"), chosen.map { it.optionId })
    }

    @Test
    fun aRequiredGroupKeepsItsLastOption() {
        val milk = group(max = 1, required = true)

        val chosen = toggledSelection(listOf(pick(soy)), milk, soy)

        assertEquals(listOf("soy"), chosen.map { it.optionId })
    }

    @Test
    fun aCapOfZeroIsTreatedAsOneRatherThanBlockingEverything() {
        // max_select defaults to 1; a 0 would mean "choose nothing", which no till can honour.
        val milk = group(max = 0)

        val chosen = toggledSelection(emptyList(), milk, soy)

        assertEquals(listOf("soy"), chosen.map { it.optionId })
    }

    @Test
    fun anotherGroupIsNotDisturbedByThisOne() {
        val milk = group(max = 2)
        val other = GroupWithOther()

        val chosen = toggledSelection(listOf(other), milk, soy)

        assertEquals(2, chosen.size)
        assertEquals("other", chosen.first().optionId)
    }

    @Test
    fun aGroupAskingForTwoKeepsItsLastTwo() {
        val sauces = ModifierGroup(name = "Sauces", options = listOf(soy, oat), maxSelect = 3, minSelect = 2)

        var chosen = toggledSelection(emptyList(), sauces, soy)
        chosen = toggledSelection(chosen, sauces, oat)
        val refused = toggledSelection(chosen, sauces, soy)

        assertEquals(listOf("soy", "oat"), refused.map { it.optionId })
    }

    @Test
    fun aMinimumOfOneBehavesLikeRequired() {
        val sauce = ModifierGroup(name = "Sauce", options = listOf(soy, oat), maxSelect = 1, minSelect = 1)

        val chosen = toggledSelection(listOf(pick(soy)), sauce, soy)

        assertEquals(listOf("soy"), chosen.map { it.optionId })
    }

    @Test
    fun theFloorIsTheHigherOfRequiredAndTheMinimum() {
        // is_required means "at least one"; min_select says how many; a group can carry both.
        assertEquals(0, ModifierGroup("Plain", listOf(soy)).floor())
        assertEquals(1, ModifierGroup("Required", listOf(soy), required = true).floor())
        assertEquals(2, ModifierGroup("Two", listOf(soy), required = true, minSelect = 2).floor())
        assertEquals(2, ModifierGroup("Two, not required", listOf(soy), minSelect = 2).floor())
    }

    private fun GroupWithOther() = SelectedModifier("other", "Something else", 0.0)
}
