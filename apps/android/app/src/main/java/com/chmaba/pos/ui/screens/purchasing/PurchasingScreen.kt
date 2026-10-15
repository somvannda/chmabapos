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
    Draft("Draft", BadgeTone.Neutral),
}

/** A purchase order. Placeholder data until the purchasing endpoint is wired. */
data class PurchaseOrder(
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

@Composable
fun PurchasingScreen(
    modifier: Modifier = Modifier,
    viewModel: com.chmaba.pos.ui.screens.store.PurchasingViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel(),
    // No endpoint supplies these yet, so the list stays empty rather than showing
    // sample rows that look like real stock.
    suggestions: List<ReorderSuggestion> = emptyList(),
    onOpenOrder: (String) -> Unit = {},
    onNewOrder: () -> Unit = {},
    onCreateOrdersForSuggestions: () -> Unit = {},
    /** Whether the plan includes purchasing; creating a purchase order needs it. */
    planAllowsPurchasing: Boolean = true,
) {
    val orders = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    var filter by remember { mutableStateOf(PoFilter.All) }
    val visible = if (filter.status == null) orders else orders.filter { it.status == filter.status }

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
                onClick = onNewOrder,
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
                            "${order.supplier} · ${order.lineCount} lines · ${order.date}",
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
