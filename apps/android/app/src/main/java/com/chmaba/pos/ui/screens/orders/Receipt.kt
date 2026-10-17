package com.chmaba.pos.ui.screens.orders

/**
 * The receipt, as text to send.
 *
 * The order detail already holds everything a receipt says, and none of it needs a printer: the
 * reader shares it to whoever wants it. This is why the button that used to say it was not in the
 * app is now a share - the app still cannot drive a printer, and that is a transport it does not
 * have, but *a receipt* needs no transport to leave the device.
 *
 * The totals come out in the order they are read, and an optional line appears only when the order
 * had one, so a plain sale is not padded with a zero discount or an absent change.
 */
fun receiptText(order: OrderDetail, storeName: String): String = buildString {
    appendLine(storeName)
    appendLine(order.number)
    appendLine(order.meta)
    appendLine()
    order.lines.forEach { line ->
        appendLine(line.name)
        line.note?.takeIf { it.isNotBlank() }?.let { appendLine("  " + it) }
        appendLine("  " + line.amount)
    }
    appendLine()
    appendLine(aligned("Subtotal") + order.subtotal)
    order.discount?.takeIf { it.isNotBlank() }?.let { appendLine(aligned("Discount") + it) }
    appendLine(aligned("Tax") + order.tax)
    appendLine(aligned("Total") + order.total)
    appendLine()
    appendLine(aligned(order.method) + order.paid)
    order.change?.takeIf { it.isNotBlank() }?.let { appendLine(aligned("Change") + it) }
}

/** Labels and amounts line up in plain text, which is all the share sheet will preserve. */
private fun aligned(label: String): String = label.padEnd(20)
