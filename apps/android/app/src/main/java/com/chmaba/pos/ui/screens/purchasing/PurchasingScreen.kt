package com.chmaba.pos.ui.screens.purchasing

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaSurface

private val PurchasingBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val YellowSoft = Color(0xFFFFF6DF)

/** Purchase-order lifecycle, matching the web's PO states. */
enum class PurchaseStatus(val label: String, val tone: BadgeTone) {
    Open("Open", BadgeTone.Blue),
    Partial("Partial", BadgeTone.Yellow),
    Received("Received", BadgeTone.Green),
    Cancelled("Cancelled", BadgeTone.Neutral),
    Draft("Draft", BadgeTone.Neutral),
}

/** A purchase order. Placeholder data until the purchasing endpoint is wired. */
data class PurchaseOrder(
    /** The API's id, for receiving it; [reference] is the number a person reads. */
    val id: String,
    val reference: String,
    val supplier: String,
    val lineCount: Int,
    val date: String,
    val status: PurchaseStatus,
    val total: String,
)

/** A suggested reorder derived from low stock, not stored data. */
data class ReorderSuggestion(
    val productName: String,
    val onHand: Int,
    val suggestedQuantity: Int,
)

/** Status filters. The prototype showed a chip strip per status; "All" is added
 *  so the default view isn't empty when no order is Open. */
private enum class PoFilter(val label: String, val status: PurchaseStatus?) {
    All("All", null),
    Open("Open", PurchaseStatus.Open),
    Partial("Partial", PurchaseStatus.Partial),
    Received("Received", PurchaseStatus.Received),
    Draft("Draft", PurchaseStatus.Draft),
}

/**
 * "1 line" or "2 lines" - the row said "1 lines" for every single-line order, which is every order
 * raised by the form this app now has. Kept as a named rule so it can be held to a test.
 */
fun lineWording(count: Int): String = count.toString() + (if (count == 1) " line" else " lines")

/**
 * One line of the purchase order being built.
 *
 * `PurchaseCreateBody.items` has always taken a list and the form could only ever send one, so a
 * delivery of five things became five orders. [name] is carried for the sheet's own list: the wire
 * body only needs the id.
 */
data class PoLine(val productId: String, val name: String, val quantity: Int)

/**
 * The lines after adding one: the same product again adds to the quantity it already has rather
 * than appearing twice, which is what a person reading the list expects.
 *
 * Pure, so a test can hold it.
 */
fun withLine(lines: List<PoLine>, line: PoLine): List<PoLine> {
    val existing = lines.indexOfFirst { it.productId == line.productId }
    if (existing < 0) return lines + line
    return lines.toMutableList().also {
        it[existing] = it[existing].copy(quantity = it[existing].quantity + line.quantity)
    }
}

/** And without one, for the sheet's remove. */
fun withoutLine(lines: List<PoLine>, productId: String): List<PoLine> =
    lines.filterNot { it.productId == productId }

@Composable
fun PurchasingScreen(
    modifier: Modifier = Modifier,
    viewModel: com.chmaba.pos.ui.screens.store.PurchasingViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel(),
    // No endpoint supplies these yet, so the list stays empty rather than showing
    // sample rows that look like real stock.
    suggestions: List<ReorderSuggestion> = emptyList(),
    onOpenOrder: (String) -> Unit = {},
    onCreateOrdersForSuggestions: () -> Unit = {},
    /** Whether the plan includes purchasing; creating a purchase order needs it. */
    planAllowsPurchasing: Boolean = true,
) {
    val orders = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    var filter by remember { mutableStateOf(PoFilter.All) }
    // The order form. The API has always taken a list of lines and a supplier; the form could only
    // ever send one line and never a supplier, so a delivery of five things became five orders.
    // Nothing is invented here - products and suppliers come from the server, and the refusal for a
    // variant product comes from the server too, naming it.
    var raising by remember { mutableStateOf(false) }
    var pickedProduct by remember { mutableStateOf("") }
    var pickedSupplier by remember { mutableStateOf("") }
    var quantity by remember { mutableStateOf("1") }
    val lines = remember { androidx.compose.runtime.mutableStateListOf<PoLine>() }
    // The order whose Receive was tapped: receiving cannot be undone, so it is confirmed first.
    var receivingOrder by remember { mutableStateOf<PurchaseOrder?>(null) }

    if (raising) {
        androidx.compose.material3.ModalBottomSheet(
            onDismissRequest = { raising = false },
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(20.dp),
            ) {
                Text(
                    "Raise a purchase order",
                    color = ChmabaGray900,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "What you are buying, and how many. The order is recorded as Ordered; the stock " +
                        "moves when it is received, not now.",
                    color = ChmabaGray500,
                    fontSize = 11.5.sp,
                    lineHeight = 16.sp,
                )
                Spacer(Modifier.height(14.dp))
                // A supplier is optional on the server, so "No supplier" is a real choice here
                // rather than a blank the reader has to guess about.
                Text("Supplier", color = ChmabaGray500, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    ChmabaButton(
                        onClick = { pickedSupplier = "" },
                        text = "No supplier",
                        variant = com.chmaba.pos.ui.components.ButtonVariant.Primary,
                        size = com.chmaba.pos.ui.components.ButtonSize.Small,
                        enabled = pickedSupplier.isNotEmpty(),
                    )
                    viewModel.formSuppliers.forEach { supplier ->
                        val id = supplier.id.orEmpty()
                        ChmabaButton(
                            onClick = { pickedSupplier = id },
                            text = supplier.name,
                            variant = com.chmaba.pos.ui.components.ButtonVariant.Primary,
                            size = com.chmaba.pos.ui.components.ButtonSize.Small,
                            enabled = id != pickedSupplier,
                        )
                    }
                }
                Spacer(Modifier.height(14.dp))
                Text("Product", color = ChmabaGray500, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    viewModel.formProducts.forEach { product ->
                        val name = product.name
                        val id = product.id ?: ""
                        ChmabaButton(
                            onClick = { pickedProduct = id },
                            text = name,
                            variant = com.chmaba.pos.ui.components.ButtonVariant.Primary,
                            size = com.chmaba.pos.ui.components.ButtonSize.Small,
                            // The picked one reads as pressed rather than as another choice.
                            enabled = id != pickedProduct,
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                com.chmaba.pos.ui.components.ChmabaTextField(
                    value = quantity,
                    onValueChange = { quantity = it },
                    label = "Quantity",
                )
                Spacer(Modifier.height(10.dp))
                ChmabaButton(
                    onClick = {
                        val picked = viewModel.formProducts.firstOrNull { it.id == pickedProduct }
                        val count = quantity.toIntOrNull() ?: 0
                        if (picked != null && count > 0) {
                            val next = withLine(
                                lines,
                                PoLine(picked.id.orEmpty(), picked.name, count),
                            )
                            lines.clear()
                            lines.addAll(next)
                            // Ready for the next thing in the same delivery.
                            pickedProduct = ""
                            quantity = "1"
                        }
                    },
                    text = "Add line",
                    modifier = Modifier.fillMaxWidth(),
                    variant = com.chmaba.pos.ui.components.ButtonVariant.Primary,
                    size = com.chmaba.pos.ui.components.ButtonSize.Small,
                    enabled = pickedProduct.isNotBlank() &&
                        (quantity.toIntOrNull() ?: 0) > 0 &&
                        !viewModel.creating,
                )
                if (lines.isNotEmpty()) {
                    Spacer(Modifier.height(14.dp))
                    Text("This order", color = ChmabaGray500, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(6.dp))
                    lines.forEach { line ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                "${line.quantity} · ${line.name}",
                                color = ChmabaGray900,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f),
                            )
                            ChmabaButton(
                                onClick = {
                                    val next = withoutLine(lines, line.productId)
                                    lines.clear()
                                    lines.addAll(next)
                                },
                                text = "Remove",
                                size = com.chmaba.pos.ui.components.ButtonSize.Small,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
                ChmabaButton(
                    onClick = {
                        viewModel.raiseOrder(lines.toList(), pickedSupplier.ifBlank { null }) {
                            raising = false
                            lines.clear()
                        }
                    },
                    text = when {
                        viewModel.creating -> "Raising…"
                        lines.size > 1 -> "Raise order · ${lineWording(lines.size)}"
                        else -> "Raise order"
                    },
                    modifier = Modifier.fillMaxWidth(),
                    variant = com.chmaba.pos.ui.components.ButtonVariant.Primary,
                    size = com.chmaba.pos.ui.components.ButtonSize.Large,
                    enabled = lines.isNotEmpty() && !viewModel.creating,
                )
                viewModel.createdReference?.let { made ->
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "Raised " + made + ". It is on the list, marked Open.",
                        color = ChmabaGray900,
                        fontSize = 11.5.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
                viewModel.createError?.let { problem ->
                    Spacer(Modifier.height(10.dp))
                    Text(problem, color = ChmabaGray500, fontSize = 11.5.sp, lineHeight = 16.sp)
                }
                Spacer(Modifier.height(8.dp))
            }
        }
    }
    val visible = if (filter.status == null) orders else orders.filter { it.status == filter.status }

    // Receiving moves stock that no tap can put back, so it is asked about rather than assumed.
    receivingOrder?.let { order ->
        androidx.compose.material3.ModalBottomSheet(
            onDismissRequest = { receivingOrder = null },
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp),
            ) {
                Text(
                    "Receive " + order.reference + "?",
                    color = ChmabaGray900,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "Every line goes onto the shelf and the order closes. This cannot be undone from here.",
                    color = ChmabaGray500,
                    fontSize = 11.5.sp,
                    lineHeight = 16.sp,
                )
                viewModel.receiveError?.let { problem ->
                    Spacer(Modifier.height(10.dp))
                    Text(problem, color = ChmabaGray900, fontSize = 11.5.sp, lineHeight = 16.sp)
                }
                Spacer(Modifier.height(16.dp))
                ChmabaButton(
                    onClick = {
                        viewModel.receive(order.id, order.reference) { receivingOrder = null }
                    },
                    text = if (viewModel.receiving == order.reference) "Receiving…" else "Receive it",
                    modifier = Modifier.fillMaxWidth(),
                    variant = ButtonVariant.Primary,
                    size = ButtonSize.Large,
                    enabled = viewModel.receiving == null,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "Not yet",
                    color = ChmabaGray500,
                    fontSize = 12.5.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { receivingOrder = null }
                        .padding(vertical = 12.dp),
                )
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(PurchasingBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Purchasing",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text("Purchase orders and receiving.", color = ChmabaGray500, fontSize = 12.5.sp)
            }
            ChmabaButton(
                onClick = {
                    viewModel.clearCreateResult()
                    viewModel.loadFormOptions()
                    pickedProduct = ""
                    pickedSupplier = ""
                    quantity = "1"
                    lines.clear()
                    raising = true
                },
                text = "New PO",
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
                // Creating a purchase order needs the purchasing feature. Disabling it
                // and saying why beats a form that only fails on submit.
                enabled = planAllowsPurchasing,
                leadingIcon = {
                    Icon(ChmabaIcons.Plus, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                },
            )
        }

        if (!planAllowsPurchasing) {
            Spacer(Modifier.height(10.dp))
            Text(
                "Your plan does not include purchasing, so purchase orders cannot be created here.",
                color = ChmabaGray500,
                fontSize = 11.sp,
                lineHeight = 15.sp,
            )
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            MiniStat(
                label = "Open",
                value = orders.count { it.status == PurchaseStatus.Open || it.status == PurchaseStatus.Partial }.toString(),
                background = YellowSoft,
                modifier = Modifier.weight(1f),
            )
            MiniStat(
                label = "Received",
                value = orders.count { it.status == PurchaseStatus.Received }.toString(),
                background = Color(0xFFEFF9E6),
                modifier = Modifier.weight(1f),
            )
            MiniStat(
                label = "Draft",
                value = orders.count { it.status == PurchaseStatus.Draft }.toString(),
                background = ChmabaLavender,
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(14.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            PoFilter.entries.forEach { entry ->
                val active = entry == filter
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(9.dp))
                        .background(if (active) ChmabaBlue else ChmabaSurface)
                        .clickable { filter = entry }
                        .padding(horizontal = 12.dp, vertical = 7.dp),
                ) {
                    Text(
                        entry.label,
                        color = if (active) Color.White else ChmabaGray500,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        Spacer(Modifier.height(14.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            visible.forEachIndexed { index, order ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpenOrder(order.reference) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            order.reference,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.ExtraBold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "${order.supplier} · ${lineWording(order.lineCount)} · ${order.date}",
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    ChmabaBadge(order.status.label, order.status.tone)
                    Spacer(Modifier.width(10.dp))
                    Text(
                        order.total,
                        color = ChmabaGray900,
                        fontSize = 12.5.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    // Only an ordered one can be received; the API answers 409 otherwise, and
                    // offering a button that always fails is worse than not offering it.
                    if (order.status == PurchaseStatus.Open) {
                        Spacer(Modifier.width(10.dp))
                        ChmabaButton(
                            onClick = { receivingOrder = order },
                            text = if (viewModel.receiving == order.reference) "Receiving…" else "Receive",
                            size = ButtonSize.Small,
                            enabled = viewModel.receiving == null,
                        )
                    }
                }
            }
            com.chmaba.pos.ui.components.LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading purchase orders…",
                failedTitle = "Could not load purchases",
                onRetry = { viewModel.load() },
            )
            if (visible.isEmpty() && viewModel.state is com.chmaba.pos.data.store.LoadState.Ready) {
                Text(
                    "No purchase orders in this view.",
                    color = ChmabaGray400,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(20.dp),
                )
            }
        }

        // Reorder suggestions need an inventory-derived source that no endpoint
        // exposes yet, so the card is hidden rather than shown empty behind a
        // "0 items" badge.
        if (suggestions.isNotEmpty()) {
            Spacer(Modifier.height(14.dp))

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(ChmabaSurface)
                    .padding(16.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Reorder suggestions", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                        Spacer(Modifier.height(2.dp))
                        Text("Derived from low stock", color = ChmabaGray400, fontSize = 10.sp)
                    }
                    ChmabaBadge("${suggestions.size} items", BadgeTone.Yellow)
                }

                Spacer(Modifier.height(12.dp))

                suggestions.forEachIndexed { index, suggestion ->
                    if (index > 0) Spacer(Modifier.height(10.dp))
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            suggestion.productName,
                            color = ChmabaGray900,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.weight(1f),
                        )
                        Text(
                            "${suggestion.onHand} left · order ${suggestion.suggestedQuantity}",
                            color = ChmabaGray500,
                            fontSize = 10.5.sp,
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))
                ChmabaButton(
                    onClick = onCreateOrdersForSuggestions,
                    text = "Create purchase orders",
                    modifier = Modifier.fillMaxWidth(),
                    variant = ButtonVariant.Outline,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun MiniStat(label: String, value: String, background: Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(background)
            .padding(11.dp),
    ) {
        Text(
            label.uppercase(),
            color = ChmabaGray500,
            fontSize = 8.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.6.sp,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            value,
            color = ChmabaGray900,
            fontSize = 18.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
    }
}
