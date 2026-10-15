package com.chmaba.pos.ui.screens.reports

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import com.chmaba.pos.data.reports.MixShare
import com.chmaba.pos.data.reports.ReportPeriod
import com.chmaba.pos.data.reports.ReportSummaryDto
import com.chmaba.pos.data.reports.salesMix
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.store.money
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
import com.chmaba.pos.ui.theme.ChmabaGreen
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaLimeLight
import com.chmaba.pos.ui.theme.ChmabaPeach
import com.chmaba.pos.ui.theme.ChmabaSurface

private val ReportsBg = Color(0xFFF7F7FA)
private val YellowSoft = Color(0xFFFFF6DF)
private val BarIdle = Color(0xFFDCD9FB)
private val TrackBg = Color(0xFFF0F0F4)

/** Share-bar colours, cycled in the order the server ranks the rows. */
private val ShareColors = listOf(ChmabaBlue, Color(0xFFC4F27C), ChmabaPeach, Color(0xFFB9B2FA), ChmabaGray400)

private data class Metric(
    val label: String,
    val value: String,
    val detail: String,
    val background: Color,
)

/**
 * Sales reporting, driven by `GET /reports/summary` (the endpoint the web's
 * reports view uses). The period chips refetch through the shared view model.
 */
@Composable
fun ReportsScreen(
    modifier: Modifier = Modifier,
    state: LoadState<ReportSummaryDto> = LoadState.Loading,
    period: ReportPeriod = ReportPeriod.Today,
    onSelectPeriod: (ReportPeriod) -> Unit = {},
    onRetry: () -> Unit = {},
    onExport: () -> Unit = {},
    /** True while the export is being fetched, so the button can hold. */
    exporting: Boolean = false,
    /** The API's refusal or failure for the last export. */
    exportError: String? = null,
    /** Whether this workspace's plan includes the server's invoice export. */
    planAllowsExport: Boolean = true,
) {
    val summary = (state as? LoadState.Ready)?.data

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(ReportsBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Reports",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    summary?.let { "${it.fromDate} – ${it.toDate}" } ?: "Sales for the selected period.",
                    color = ChmabaGray500,
                    fontSize = 12.5.sp,
                )
            }
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(ChmabaSurface)
                    .clickable(enabled = planAllowsExport && !exporting, onClick = onExport),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    ChmabaIcons.Download,
                    contentDescription = "Export",
                    tint = ChmabaGray500,
                    modifier = Modifier.size(17.dp),
                )
            }
        }

        if (!planAllowsExport) {
            Spacer(Modifier.height(10.dp))
            Text(
                "Exporting invoices needs a plan that includes advanced reports.",
                color = ChmabaGray500,
                fontSize = 11.sp,
                lineHeight = 15.sp,
            )
        }
        if (exportError != null) {
            Spacer(Modifier.height(8.dp))
            Text(
                exportError,
                color = Color(0xFFC2564B),
                fontSize = 11.sp,
                lineHeight = 15.sp,
            )
        }

        Spacer(Modifier.height(14.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ReportPeriod.entries.forEach { entry ->
                val active = entry == period
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(9.dp))
                        .background(if (active) ChmabaBlue else ChmabaSurface)
                        .clickable { onSelectPeriod(entry) }
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

        if (state is LoadState.Loading) {
            Notice("Loading the report…")
            return@Column
        }
        if (state is LoadState.Failed) {
            Failed(state.message, onRetry)
            return@Column
        }
        if (summary == null) {
            Notice("No report data in this period.")
            return@Column
        }

        val currency = summary.currency
        val metrics = listOf(
            Metric("Net sales", money(summary.effectiveNetRaw, currency), "After discounts & refunds", ChmabaLavender),
            Metric(
                "Transactions",
                summary.transactions.toString(),
                "${"%.1f".format(summary.averagePerDay)} avg/day",
                ChmabaLimeLight,
            ),
            Metric("Average order", money(summary.averageOrder, currency), "Net per paid order", ChmabaPeach),
            Metric(
                "Refunds",
                money(summary.refunds, currency),
                if (summary.refundsCount == 1) "1 order" else "${summary.refundsCount} orders",
                YellowSoft,
            ),
        )

        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(metrics[0], Modifier.weight(1f))
                MetricCard(metrics[1], Modifier.weight(1f))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(metrics[2], Modifier.weight(1f))
                MetricCard(metrics[3], Modifier.weight(1f))
            }
        }

        Spacer(Modifier.height(12.dp))

        // Sales by day. The API returns one row per local day that had a paid
        // order, so days with no trade are absent rather than zero.
        val days = summary.dailySales.takeLast(8)
        val peak = days.maxOfOrNull { it.value } ?: 0.0
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Sales by day", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                    Spacer(Modifier.height(2.dp))
                    Text(
                        "${summary.fromDate} – ${summary.toDate}",
                        color = ChmabaGray400,
                        fontSize = 10.sp,
                    )
                }
                ChmabaBadge(
                    if (days.size == 1) "1 day" else "${days.size} days",
                    BadgeTone.Neutral,
                )
            }
            Spacer(Modifier.height(14.dp))
            if (days.isEmpty() || peak <= 0.0) {
                Text("No paid sales in this period.", color = ChmabaGray400, fontSize = 11.5.sp)
            } else {
                AnimatedBars(days.map { (it.value / peak).toFloat().coerceIn(0.04f, 1f) })
            }
        }

        Spacer(Modifier.height(12.dp))

        val payments = salesMix(summary.paymentMethods)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Text("Payment breakdown", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(14.dp))
            if (payments.isEmpty()) {
                Text("No payments recorded in this period.", color = ChmabaGray400, fontSize = 11.5.sp)
            } else {
                payments.forEachIndexed { index, share ->
                    if (index > 0) Spacer(Modifier.height(12.dp))
                    ShareBar(share.label, share.percent, ShareColors[index % ShareColors.size])
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        val categories = salesMix(summary.categorySales)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Text("Top categories", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(14.dp))
            if (categories.isEmpty()) {
                Text("No category sales in this period.", color = ChmabaGray400, fontSize = 11.5.sp)
            } else {
                categories.forEachIndexed { index, share ->
                    if (index > 0) Spacer(Modifier.height(12.dp))
                    CategoryRow(share, money(share.amount, currency), ShareColors[index % ShareColors.size])
                }
            }
        }

        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun CategoryRow(share: MixShare, amount: String, dot: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(dot),
        )
        Spacer(Modifier.width(10.dp))
        Text(
            share.label,
            color = ChmabaGray900,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.weight(1f),
        )
        Text(
            "$amount · ${share.percent}%",
            color = ChmabaGray900,
            fontSize = 12.sp,
            fontWeight = FontWeight.ExtraBold,
        )
    }
}

@Composable
private fun Notice(message: String) {
    Text(message, color = ChmabaGray400, fontSize = 12.sp, modifier = Modifier.padding(20.dp))
}

/** Shown when `GET /reports/summary` fails. */
@Composable
private fun Failed(message: String, onRetry: () -> Unit) {
    Column(modifier = Modifier.padding(20.dp)) {
        Text("Could not load the report", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
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
private fun AnimatedBars(heights: List<Float>) {
    var grown by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { grown = true }
    val growth by animateFloatAsState(
        targetValue = if (grown) 1f else 0.04f,
        animationSpec = tween(durationMillis = 550),
        label = "report-bars",
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(130.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        heights.forEachIndexed { index, fraction ->
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight(fraction * growth)
                    .clip(RoundedCornerShape(topStart = 5.dp, topEnd = 5.dp))
                    .background(if (index == heights.lastIndex) ChmabaBlue else BarIdle),
            )
        }
    }
}

@Composable
private fun ShareBar(label: String, percent: Int, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            label,
            color = ChmabaGray900,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.width(64.dp),
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .height(6.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(TrackBg),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(percent / 100f)
                    .fillMaxHeight()
                    .clip(RoundedCornerShape(99.dp))
                    .background(color),
            )
        }
        Spacer(Modifier.width(10.dp))
        Text(
            "$percent%",
            color = ChmabaGray900,
            fontSize = 12.sp,
            fontWeight = FontWeight.ExtraBold,
            modifier = Modifier.width(38.dp),
        )
    }
}

@Composable
private fun MetricCard(metric: Metric, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(metric.background)
            .padding(14.dp),
    ) {
        Text(
            metric.label.uppercase(),
            color = ChmabaGray500,
            fontSize = 8.5.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.7.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            metric.value,
            color = ChmabaGray900,
            fontSize = 18.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(3.dp))
        Text(metric.detail, color = ChmabaGray400, fontSize = 9.sp, lineHeight = 13.sp)
    }
}
