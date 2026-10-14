package com.chmaba.pos.ui.screens.orders

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
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.OrderStatus
import com.chmaba.pos.ui.components.StatusBadge
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaGreen
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface

private val OrdersBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val YellowSoft = Color(0xFFFFF6DF)

/**
 * Order rows as returned by the store orders endpoint. Placeholder data until the
 * API is wired — the shape mirrors the web's order list (number, customer, time,
 * tender, status, total).
 */
data class OrderSummary(
    val number: String,
    val customer: String,
    val time: String,
    val method: String,
    val methodTone: BadgeTone,
    val status: OrderStatus,
    val total: String,
)

data class OrderLine(
    val name: String,
    val note: String?,
    val amount: String,
)

data class OrderDetail(
    val number: String,
    val meta: String,
    val status: OrderStatus,
    val lines: List<OrderLine>,
    val subtotal: String,
    val discount: String?,
    val tax: String,
    val total: String,
    val method: String,
    val paid: String,
    val reference: String,
)

private val SAMPLE_ORDERS = listOf(
    OrderSummary("#1048", "Walk-in", "10:42 AM", "KHQR", BadgeTone.Violet, OrderStatus.Paid, "$24.50"),
    OrderSummary("#1047", "Sokha Lim", "10:36 AM", "Cash", BadgeTone.Green, OrderStatus.Paid, "$8.70"),
    OrderSummary("#1046", "Dara Vong", "10:20 AM", "KHQR", BadgeTone.Violet, OrderStatus.Pending, "$18.20"),
    OrderSummary("#1045", "Walk-in", "10:13 AM", "KHQR", BadgeTone.Violet, OrderStatus.Pickup, "$31.00"),
    OrderSummary("#1044", "Walk-in", "09:58 AM", "Cash", BadgeTone.Green, OrderStatus.Cancelled, "$6.40"),
)

private val SAMPLE_DETAIL = OrderDetail(
    number = "#1048",
    meta = "Walk-in · 8 Oct, 10:42 AM",
    status = OrderStatus.Paid,
    lines = listOf(
        OrderLine("Iced Latte × 2", "Large · Oat milk", "$9.00"),
        OrderLine("Matcha Cloud × 1", null, "$5.25"),
        OrderLine("Butter Croissant × 2", null, "$6.40"),
    ),
    subtotal = "$20.65",
    discount = "−$1.20",
    tax = "$2.05",
    total = "$24.50",
    method = "KHQR",
    paid = "$24.50",
    reference = "Bakong ref · 0842 1193 7745",
)

private enum class OrderFilter(val label: String, val status: OrderStatus?) {
    All("All orders", null),
    Paid("Paid", OrderStatus.Paid),
    Pending("Pending", OrderStatus.Pending),
    Pickup("Pickup", OrderStatus.Pickup),
    Cancelled("Cancelled", OrderStatus.Cancelled),
}

@Composable
fun OrdersScreen(
    modifier: Modifier = Modifier,
    storeName: String = "Main Counter",
    state: LoadState<List<OrderSummary>> = LoadState.Ready(SAMPLE_ORDERS),
    onOpenOrder: (String) -> Unit = {},
    onRetry: () -> Unit = {},
) {
    val orders = (state as? LoadState.Ready)?.data.orEmpty()
    var filter by remember { mutableStateOf(OrderFilter.All) }
    val visible = if (filter.status == null) orders else orders.filter { it.status == filter.status }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(OrdersBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Orders",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text("Every order from $storeName.", color = ChmabaGray500, fontSize = 12.5.sp)
            }
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(ChmabaSurface)
                    .clickable { },
                contentAlignment = Alignment.Center,
            ) {
                Icon(ChmabaIcons.Refresh, contentDescription = "Refresh", tint = ChmabaGray500, modifier = Modifier.size(17.dp))
            }
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MiniStat("Orders loaded", orders.size.toString(), ChmabaLavender, Modifier.weight(1f))
            MiniStat("Paid", orders.count { it.status == OrderStatus.Paid }.toString(), Color(0xFFEFF9E6), Modifier.weight(1f))
            MiniStat("Pending", orders.count { it.status == OrderStatus.Pending }.toString(), YellowSoft, Modifier.weight(1f))
        }

        Spacer(Modifier.height(14.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OrderFilter.entries.forEach { entry ->
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
                        .clickable { onOpenOrder(order.number) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            order.number,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.ExtraBold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "${order.customer} · ${order.time}",
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    ChmabaBadge(order.method, order.methodTone)
                    Spacer(Modifier.width(10.dp))
                    StatusBadge(order.status)
                    Spacer(Modifier.width(10.dp))
                    Text(
                        order.total,
                        color = ChmabaGray900,
                        fontSize = 12.5.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                }
            }
            if (state is LoadState.Loading) {
                OrdersNotice("Loading orders…")
            } else if (state is LoadState.Failed) {
                OrdersFailed((state as LoadState.Failed).message, onRetry)
            } else if (visible.isEmpty()) {
                OrdersNotice("No orders match this filter.")
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun OrdersNotice(message: String) {
    Text(
        message,
        color = ChmabaGray400,
        fontSize = 12.sp,
        modifier = Modifier.padding(20.dp),
    )
}

/** Shown when `GET /orders` fails — keeps the reason visible and offers a retry. */
@Composable
private fun OrdersFailed(message: String, onRetry: () -> Unit) {
    Column(modifier = Modifier.padding(20.dp)) {
        Text(
            "Could not load orders",
            color = ChmabaGray900,
            fontSize = 13.sp,
            fontWeight = FontWeight.ExtraBold,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            message,
            color = ChmabaGray500,
            fontSize = 11.5.sp,
            lineHeight = 17.sp,
        )
        Spacer(Modifier.height(12.dp))
        ChmabaButton(
            onClick = onRetry,
            text = "Try again",
            variant = ButtonVariant.Outline,
            size = ButtonSize.Small,
        )
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

@Composable
fun OrderDetailScreen(
    modifier: Modifier = Modifier,
    detail: OrderDetail = SAMPLE_DETAIL,
    onBack: () -> Unit = {},
    onPrintReceipt: () -> Unit = {},
    onRefund: () -> Unit = {},
    onCancel: () -> Unit = {},
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(OrdersBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(ChmabaSurface)
                    .clickable(onClick = onBack),
                contentAlignment = Alignment.Center,
            ) {
                Icon(ChmabaIcons.ChevronLeft, contentDescription = "Back", tint = ChmabaGray500, modifier = Modifier.size(17.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    detail.number,
                    color = ChmabaGray900,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(detail.meta, color = ChmabaGray500, fontSize = 11.sp)
            }
            StatusBadge(detail.status)
        }

        Spacer(Modifier.height(16.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Text("Items", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(12.dp))
            detail.lines.forEachIndexed { index, line ->
                if (index > 0) Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.Top) {
                    Column(Modifier.weight(1f)) {
                        Text(line.name, color = ChmabaGray900, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        if (line.note != null) {
                            Spacer(Modifier.height(2.dp))
                            Text(line.note, color = ChmabaGray400, fontSize = 10.sp)
                        }
                    }
                    Text(line.amount, color = ChmabaGray900, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(Modifier.height(14.dp))
            Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
            Spacer(Modifier.height(12.dp))

            TotalRow("Subtotal", detail.subtotal, muted = true)
            if (detail.discount != null) {
                Spacer(Modifier.height(8.dp))
                TotalRow("Discount", detail.discount, valueColor = ChmabaRed, muted = true)
            }
            Spacer(Modifier.height(8.dp))
            TotalRow("Tax", detail.tax, muted = true)
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Total", color = ChmabaGray900, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold)
                Text(detail.total, color = ChmabaGray900, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold)
            }
        }

        Spacer(Modifier.height(12.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Text("Payment", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                ChmabaBadge(detail.method, BadgeTone.Violet)
                Text(detail.paid, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(8.dp))
            Text(detail.reference, color = ChmabaGray400, fontSize = 10.sp)
        }

        Spacer(Modifier.height(14.dp))

        ChmabaButton(
            onClick = onPrintReceipt,
            text = "Print receipt",
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            leadingIcon = { Icon(ChmabaIcons.Printer, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp)) },
        )
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ChmabaButton(
                onClick = onRefund,
                text = "Refund",
                modifier = Modifier.weight(1f),
                variant = ButtonVariant.Danger,
            )
            ChmabaButton(
                onClick = onCancel,
                text = "Cancel order",
                modifier = Modifier.weight(1f),
                variant = ButtonVariant.Outline,
            )
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun TotalRow(label: String, value: String, muted: Boolean = false, valueColor: Color? = null) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = if (muted) ChmabaGray500 else ChmabaGray900, fontSize = 12.sp)
        Text(
            value,
            color = valueColor ?: ChmabaGray900,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}
