package com.chmaba.pos.data.catalog

/**
 * The serial numbers a receipt claims, read from the one box the Receive form offers.
 *
 * The web POS takes the same field the same way - splitting on commas and newlines - so a cashier
 * pasting a column out of a delivery note and one typing "SN-1, SN-2" both get what they meant.
 *
 * Returns null when the text says nothing, so "no serial numbers entered" and "a blank entry among
 * them" stay different facts for the caller to describe.
 */
fun parseSerialNumbers(text: String): List<String>? =
    text.split(',', '\n').map { it.trim() }.filter { it.isNotEmpty() }.ifEmpty { null }

/**
 * Why the entered serial numbers cannot accompany [quantity] units, or null when they can.
 *
 * The API answers a serial-tracked receipt without them with "Provide one serial per unit received",
 * and a mistyped count would otherwise be spent on a round trip only to be refused. The web POS
 * applies the same rule before it sends, so this is parity rather than invention.
 *
 * A quantity that does not parse is not this function's business: the Save button is already off,
 * and complaining about serials for a blank quantity would blame the wrong field.
 */
fun serialProblem(quantity: Int?, text: String): String? {
    val needed = quantity ?: return null
    val count = parseSerialNumbers(text)?.size ?: 0
    return when {
        count == needed -> null
        count == 0 -> "Enter one serial number per unit - $needed in all."
        else -> "That is $count serial number${plural(count)} for $needed unit${plural(needed)}."
    }
}

private fun plural(count: Int): String = if (count == 1) "" else "s"
