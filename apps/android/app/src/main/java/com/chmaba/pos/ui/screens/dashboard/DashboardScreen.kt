package com.chmaba.pos.ui.screens.dashboard

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.chmaba.pos.data.reports.ReportPeriod
import com.chmaba.pos.data.reports.ReportSummaryDto
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.store.money
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray300
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray700
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaGreen
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaLimeLight
import com.chmaba.pos.ui.theme.ChmabaPeach
import com.chmaba.pos.ui.theme.ChmabaSurface
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

private val YellowSoft = Color(0xFFFFF6DF)
private val TrackBg = Color(0xFFF0F0F4)

/** The three windows the Overview offers, matching lib/dashboard.js `dashboardPeriods`. */
private val DashboardPeriods = listOf(ReportPeriod.Today, ReportPeriod.Week, ReportPeriod.ThisMonth)

private fun timeGreeting(): String = when (Calendar.getInstance().get(Calendar.HOUR_OF_DAY)) {
    in 0..11 -> "Good morning"
    in 12..17 -> "Good afternoon"
    else -> "Good evening"
}

private fun todayLabel(): String =
    SimpleDateFormat("EEEE, MMMM d, yyyy", Locale.US).format(Date())

/**
 * Workspace overview, driven by `GET /reports/summary` — the endpoint the web
 * dashboard reads through lib/dashboard.js. The four headline metrics are the
 * web's `headlineMetrics` set (net sales, transactions, average order, items
 * sold), and the breakdowns come from the same payload.
 */
@Composable
fun DashboardScreen(
    modifier: Modifier = Modifier,
    greetingName: String = "there",
    storeName: String = "your store",
    state: LoadState<ReportSummaryDto> = LoadState.Loading,
    period: ReportPeriod = ReportPeriod.Today,
    onSelectPeriod: (ReportPeriod) -> Unit = {},
    onRetry: () -> Unit = {},
    onNewSale: () -> Unit = {},
    onOpenOrders: () -> Unit = {},
    onOpenProducts: () -> Unit = {},
    onOpenInventory: () -> Unit = {},
    onOpenTeam: () -> Unit = {},
    onOpenReports: () -> Unit = {},
    onOpenMenu: () -> Unit = {},
) {
    var revealed by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { revealed = true }

    val summary = (state as? LoadState.Ready)?.data

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFFF7F7FA))
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Reveal(0, revealed) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircleIcon(ChmabaIcons.Menu, label = "Open menu", onClick = onOpenMenu)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(ChmabaGreen),
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            "$storeName · open",
                            color = ChmabaGray500,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    Text(
                        "Dashboard",
                        color = ChmabaGray900,
                        fontSize = 19.sp,
                        fontWeight = FontWeight.ExtraBold,
                        letterSpacing = (-0.05).sp,
                    )
                }
                CircleIcon(ChmabaIcons.Bell)
                Spacer(Modifier.width(8.dp))
                Box(
                    modifier = Modifier
                        .size(34.dp)
                        .clip(CircleShape)
                        .background(Color(0xFFD7C0A2)),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        greetingName.split(" ")
                            .mapNotNull { it.firstOrNull()?.uppercaseChar()?.toString() }
                            .take(2)
                            .joinToString("")
                            .ifBlank { "?" },
                        color = Color(0xFF4C3B2D),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                }
            }
        }

        Spacer(Modifier.height(18.dp))

        Reveal(1, revealed) {
            Column {
                Text(todayLabel(), color = ChmabaGray500, fontSize = 11.sp)
                Spacer(Modifier.height(6.dp))
                Text(
                    // greetingName is the full name so the avatar can take two
                    // initials; the greeting itself uses the first word only.
                    "${timeGreeting()}, ${greetingName.substringBefore(' ')}.",
                    color = ChmabaGray900,
                    fontSize = 22.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "Here is what is happening at $storeName today.",
                    color = ChmabaGray500,
                    fontSize = 12.5.sp,
                )
                Spacer(Modifier.height(16.dp))
                ChmabaButton(
                    onClick = onNewSale,
                    text = "New sale",
                    modifier = Modifier.fillMaxWidth(),
                    leadingIcon = {
                        Icon(ChmabaIcons.Plus, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                    },
                )
            }
        }

        Spacer(Modifier.height(12.dp))

        if (state is LoadState.Loading) {
            Notice("Loading today's numbers…")
        } else if (state is LoadState.Failed) {
            Failed(state.message, onRetry)
        } else if (summary == null) {
            Notice("No sales reported for this period.")
        } else {
            val currency = summary.currency

            Reveal(2, revealed) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard(
                            label = "Net sales",
                            value = money(summary.effectiveNetRaw, currency),
                            detail = "After discounts & refunds",
                            background = ChmabaLavender,
                            modifier = Modifier.weight(1f),
                        )
                        MetricCard(
                            label = "Transactions",
                            value = summary.transactions.toString(),
                            detail = "${"%.1f".format(summary.averagePerDay)} avg/day",
                            background = ChmabaLimeLight,
                            modifier = Modifier.weight(1f),
                        )
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard(
                            label = "Average order",
                            value = money(summary.averageOrder, currency),
                            detail = "Net per paid order",
                            background = ChmabaPeach,
                            modifier = Modifier.weight(1f),
                        )
                        MetricCard(
                            label = "Items sold",
                            value = summary.itemsSold.roundToInt().toString(),
                            detail = "Units across paid orders",
                            background = YellowSoft,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }

            Spacer(Modifier.height(12.dp))

            Reveal(3, revealed) {
                SalesOverviewCard(
                    summary = summary,
                    currency = currency,
                    period = period,
                    onSelectPeriod = onSelectPeriod,
                )
            }

            Spacer(Modifier.height(12.dp))

            Reveal(4, revealed) {
                TopProductsCard(summary, currency, onOpenProducts)
            }

            Spacer(Modifier.height(12.dp))

            Reveal(5, revealed) {
                RecentTransactionsCard(summary, currency, storeName, onOpenOrders)
            }
        }

        Spacer(Modifier.height(12.dp))

        Reveal(6, revealed) {
            QuickActionsCard(
                onNewProduct = onOpenProducts,
                onAdjustStock = onOpenInventory,
                onInvite = onOpenTeam,
                onReports = onOpenReports,
            )
        }

        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun Reveal(index: Int, visible: Boolean, content: @Composable () -> Unit) {
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(tween(durationMillis = 300, delayMillis = index * 40)) +
            slideInVertically(tween(durationMillis = 300, delayMillis = index * 40)) { it / 8 },
    ) { content() }
}

@Composable
private fun Notice(message: String) {
    Text(message, color = ChmabaGray400, fontSize = 12.sp, modifier = Modifier.padding(20.dp))
}

/** Shown when the report fails, so the reason stays visible and retry is one tap. */
@Composable
private fun Failed(message: String, onRetry: () -> Unit) {
    Column(modifier = Modifier.padding(20.dp)) {
        Text("Could not load your numbers", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(6.dp))
        Text(message, color = ChmabaGray500, fontSize = 11.5.sp, lineHeight = 17.sp)
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
private fun CircleIcon(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String? = null,
    onClick: (() -> Unit)? = null,
) {
    Box(
        modifier = Modifier
            .size(34.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(ChmabaSurface)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = label, tint = ChmabaGray500, modifier = Modifier.size(17.dp))
    }
}

@Composable
private fun MetricCard(
    label: String,
    value: String,
    detail: String,
    background: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(background)
            .padding(14.dp),
    ) {
        Text(
            label.uppercase(),
            color = ChmabaGray500,
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.8.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            value,
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(3.dp))
        Text(detail, color = ChmabaGray400, fontSize = 9.sp)
    }
}

@Composable
private fun SalesOverviewCard(
    summary: ReportSummaryDto,
    currency: String,
    period: ReportPeriod,
    onSelectPeriod: (ReportPeriod) -> Unit,
) {
    val days = summary.dailySales.takeLast(8)
    val peak = days.maxOfOrNull { it.value } ?: 0.0
    val bars = days.map { (it.value / peak).toFloat().coerceIn(0.04f, 1f) }

    var grown by remember { mutableStateOf(false) }
    LaunchedEffect(days.size) { grown = false; grown = true }
    val growth by animateFloatAsState(
        targetValue = if (grown) 1f else 0.04f,
        animationSpec = tween(durationMillis = 550),
        label = "bar-growth",
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(ChmabaSurface)
            .padding(16.dp),
    ) {
        Text("Sales overview", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                money(summary.effectiveNetRaw, currency),
                color = ChmabaGray900,
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.05).sp,
            )
            Spacer(Modifier.width(8.dp))
            Text(
                "${money(summary.averageDailyNet, currency)} avg/day",
                color = ChmabaGray400,
                fontSize = 10.sp,
                modifier = Modifier.padding(bottom = 3.dp),
            )
        }
        Spacer(Modifier.height(14.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DashboardPeriods.forEach { entry ->
                PeriodChip(entry.label, active = entry == period) { onSelectPeriod(entry) }
            }
        }
        Spacer(Modifier.height(16.dp))
        if (bars.isEmpty() || peak <= 0.0) {
            Text("No paid sales in this period.", color = ChmabaGray400, fontSize = 11.sp)
        } else {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(110.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
                bars.forEachIndexed { index, fraction ->
                    val isLast = index == bars.lastIndex
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight(fraction * growth)
                            .clip(RoundedCornerShape(topStart = 5.dp, topEnd = 5.dp))
                            .background(if (isLast) ChmabaBlue else Color(0xFFDCD9FB)),
                    )
                }
            }
        }
    }
}

@Composable
private fun PeriodChip(label: String, active: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(9.dp))
            .background(if (active) ChmabaBlue else ChmabaSurface)
            .clickable(onClick = onClick)
            .padding(horizontal = 11.dp, vertical = 6.dp),
    ) {
        Text(
            label,
            color = if (active) Color.White else ChmabaGray500,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun TopProductsCard(
    summary: ReportSummaryDto,
    currency: String,
    onOpenProducts: () -> Unit,
) {
    val products = summary.topProducts.take(5)
    val peak = products.maxOfOrNull { it.value } ?: 0.0

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(ChmabaSurface)
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Top products", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.height(2.dp))
                Text("Best sellers in this period", color = ChmabaGray400, fontSize = 10.sp)
            }
            Text(
                "View catalog",
                color = ChmabaBlue,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(4.dp).clickableText(onOpenProducts),
            )
        }
        Spacer(Modifier.height(14.dp))
        if (products.isEmpty()) {
            Text("Nothing sold in this period yet.", color = ChmabaGray400, fontSize = 11.sp)
            return@Column
        }
        products.forEachIndexed { index, product ->
            if (index > 0) Spacer(Modifier.height(14.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "0${index + 1}",
                    color = ChmabaGray400,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.width(16.dp),
                )
                Column(Modifier.weight(1f)) {
                    Text(
                        product.name ?: "Unnamed",
                        color = ChmabaGray900,
                        fontSize = 11.5.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(Modifier.height(6.dp))
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .height(6.dp)
                            .clip(RoundedCornerShape(99.dp))
                            .background(TrackBg),
                    ) {
                        Box(
                            Modifier
                                .fillMaxWidth(if (peak > 0) (product.value / peak).toFloat() else 0f)
                                .fillMaxHeight()
                                .clip(RoundedCornerShape(99.dp))
                                .background(Color(0xFFB9B2FA)),
                        )
                    }
                }
                Spacer(Modifier.width(12.dp))
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        money(product.value, currency),
                        color = ChmabaGray900,
                        fontSize = 11.5.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    Text("${product.units} sold", color = ChmabaGray400, fontSize = 10.sp)
                }
            }
        }
    }
}

@Composable
private fun RecentTransactionsCard(
    summary: ReportSummaryDto,
    currency: String,
    storeName: String,
    onOpenOrders: () -> Unit,
) {
    val rows = summary.transactionsDetail.take(6)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(ChmabaSurface),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("Recent transactions", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.height(2.dp))
                Text("Latest activity at $storeName", color = ChmabaGray400, fontSize = 10.sp)
            }
            Text(
                "View all",
                color = ChmabaBlue,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(4.dp).clickableText(onOpenOrders),
            )
        }
        if (rows.isEmpty()) {
            Text(
                "No transactions in this period.",
                color = ChmabaGray400,
                fontSize = 11.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
            Spacer(Modifier.height(12.dp))
            return@Column
        }
        rows.forEachIndexed { index, row ->
            if (index > 0) {
                Box(Modifier.fillMaxWidth().height(1.dp).background(Color(0xFFF2F2F5)))
            }
            val method = row.paymentMethod?.takeIf { it.isNotBlank() } ?: "—"
            val isKhqr = method.equals("khqr", ignoreCase = true)
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 13.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        row.orderNumber ?: "—",
                        color = ChmabaGray900,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        "${row.unitsCount} items · ${row.timeLabel}",
                        color = ChmabaGray400,
                        fontSize = 10.sp,
                    )
                }
                Box(
                    Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(if (isKhqr) ChmabaLavender else ChmabaLimeLight)
                        .padding(horizontal = 7.dp, vertical = 3.dp),
                ) {
                    Text(
                        method,
                        color = if (isKhqr) ChmabaBlue else ChmabaGreen,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Spacer(Modifier.width(12.dp))
                Text(
                    money(row.total, currency),
                    color = ChmabaGray900,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun QuickActionsCard(
    onNewProduct: () -> Unit,
    onAdjustStock: () -> Unit,
    onInvite: () -> Unit,
    onReports: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(Color(0xFF17181C))
            .padding(16.dp),
    ) {
        Text(
            "QUICK ACTIONS",
            color = Color(0xFFC4F27C),
            fontSize = 9.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 1.2.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text("Keep things moving", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(14.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            QuickAction("New product", ChmabaIcons.Plus, onNewProduct, Modifier.weight(1f))
            QuickAction("Adjust stock", ChmabaIcons.Boxes, onAdjustStock, Modifier.weight(1f))
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            QuickAction("Invite teammate", ChmabaIcons.UserPlus, onInvite, Modifier.weight(1f))
            QuickAction("View reports", ChmabaIcons.BarChart, onReports, Modifier.weight(1f))
        }
    }
}

@Composable
private fun QuickAction(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ChmabaButton(
        onClick = onClick,
        text = label,
        modifier = modifier,
        variant = ButtonVariant.Outline,
        size = ButtonSize.Small,
        leadingIcon = {
            Icon(icon, contentDescription = null, tint = Color(0xFFC4F27C), modifier = Modifier.size(14.dp))
        },
    )
}

private fun Modifier.clickableText(onClick: () -> Unit): Modifier = clickable(onClick = onClick)
