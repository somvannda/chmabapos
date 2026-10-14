package com.chmaba.pos.ui.screens.inventory

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

private val InventoryBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val YellowSoft = Color(0xFFFFF6DF)
private val LimeSoft = Color(0xFFEFF9E6)

/**
 * A stocked product. Mirrors the web inventory view: on-hand units, the reorder
 * point, and a level derived from the two. Placeholder data until the inventory
 * endpoint is wired.
 */
data class InventoryItem(
    val productId: String,
    val name: String,
    val sku: String,
    val units: Int,
    val reorderPoint: Int,
    val color: Color,
    val initials: String,
)

private val SAMPLE_INVENTORY = listOf(
    InventoryItem("1", "Iced Latte", "COF-001", 42, 10, Color(0xFFD7C0A2), "IL"),
    InventoryItem("3", "Butter Croissant", "BAK-002", 7, 10, Color(0xFFF0C986), "BC"),
    InventoryItem("4", "Chocolate Cookie", "BAK-008", 4, 10, Color(0xFFC99E83), "CC"),
    InventoryItem("2", "Matcha Cloud", "TEA-004", 18, 10, Color(0xFFB9D7A2), "MC"),
    InventoryItem("5", "House Americano", "COF-002", 64, 10, Color(0xFFB79A83), "HA"),
)

private enum class StockFilter(val label: String) {
    All("All stock"),
    Low("Low stock"),
    Healthy("Healthy"),
}

/** Healthy above the reorder point; low at or below it; out at zero. */
private fun levelOf(item: InventoryItem): BadgeTone = when {
    item.units <= 0 -> BadgeTone.Red
    item.units <= item.reorderPoint -> BadgeTone.Yellow
    else -> BadgeTone.Green
}

private fun matches(item: InventoryItem, filter: StockFilter): Boolean = when (filter) {
    StockFilter.All -> true
    StockFilter.Low -> levelOf(item) != BadgeTone.Green
    StockFilter.Healthy -> levelOf(item) == BadgeTone.Green
}

@Composable
fun InventoryScreen(
    modifier: Modifier = Modifier,
    viewModel: com.chmaba.pos.ui.screens.store.InventoryViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel(),
    onAdjustStock: (String) -> Unit = {},
    onReceiveStock: (String) -> Unit = {},
    onExport: () -> Unit = {},
) {
    val inventory = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    var filter by remember { mutableStateOf(StockFilter.All) }
    val visible = inventory.filter { matches(it, filter) }
    val needsAttention = inventory.count { levelOf(it) != BadgeTone.Green }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(InventoryBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Inventory",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    "Keep your shelves ready for the next rush.",
                    color = ChmabaGray500,
                    fontSize = 12.5.sp,
                )
            }
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(ChmabaSurface)
                    .clickable(onClick = onExport),
                contentAlignment = Alignment.Center,
            ) {
                Icon(ChmabaIcons.Download, contentDescription = "Export", tint = ChmabaGray500, modifier = Modifier.size(17.dp))
            }
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            // All three are derived from the loaded inventory. There is no
            // stock-value figure here: InventoryRead carries cost_price/price but
            // the screen model does not, so a value would be invented.
            MiniStat("Products", inventory.size.toString(), ChmabaLavender, Modifier.weight(1f))
            MiniStat("Total units", inventory.sumOf { it.units }.toString(), LimeSoft, Modifier.weight(1f))
            MiniStat("Needs attention", needsAttention.toString(), YellowSoft, Modifier.weight(1f))
        }

        Spacer(Modifier.height(14.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            StockFilter.entries.forEach { entry ->
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
            visible.forEachIndexed { index, item ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onAdjustStock(item.productId) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        modifier = Modifier
                            .size(34.dp)
                            .clip(RoundedCornerShape(11.dp))
                            .background(item.color),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(item.initials, color = Color(0xFF343039), fontSize = 10.sp, fontWeight = FontWeight.ExtraBold)
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(item.name, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "${item.sku} · reorder at ${item.reorderPoint}",
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    ChmabaBadge(
                        text = "${item.units} units",
                        tone = levelOf(item),
                    )
                }
            }
            if (visible.isEmpty()) {
                Text(
                    "Nothing in this view.",
                    color = ChmabaGray400,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(20.dp),
                )
            }
        }

        Spacer(Modifier.height(14.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ChmabaButton(
                onClick = { visible.firstOrNull()?.let { onAdjustStock(it.productId) } },
                text = "Adjust stock",
                modifier = Modifier.weight(1f),
                variant = ButtonVariant.Outline,
                size = ButtonSize.Large,
                enabled = visible.isNotEmpty(),
            )
            ChmabaButton(
                onClick = { visible.firstOrNull()?.let { onReceiveStock(it.productId) } },
                text = "Receive stock",
                modifier = Modifier.weight(1f),
                variant = ButtonVariant.Primary,
                size = ButtonSize.Large,
                enabled = visible.isNotEmpty(),
            )
        }

        Spacer(Modifier.height(14.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Serials", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.weight(1f))
                ChmabaBadge("Serial tracking", BadgeTone.Blue)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "Electronics packs track every unit by serial / IMEI.",
                color = ChmabaGray400,
                fontSize = 10.5.sp,
                lineHeight = 15.sp,
            )
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("E2E MacBook", color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                ChmabaBadge("2 in stock", BadgeTone.Blue)
            }
            Spacer(Modifier.height(6.dp))
            Text("E2E-SN-1 · E2E-SN-2", color = ChmabaGray400, fontSize = 10.sp)
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
            fontSize = 7.5.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.5.sp,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            value,
            color = ChmabaGray900,
            fontSize = 16.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
    }
}
