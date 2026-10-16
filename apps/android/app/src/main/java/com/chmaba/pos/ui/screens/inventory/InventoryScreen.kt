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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.data.store.money
import kotlinx.coroutines.launch
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.shareCsv
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface

private val InventoryBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val YellowSoft = Color(0xFFFFF6DF)
private val LimeSoft = Color(0xFFEFF9E6)

/**
 * A stocked product. Mirrors the web inventory view: on-hand units, the reorder
 * point, and a level derived from the two.
 *
 * [unitCost] is null when the product has no cost recorded. Such a row is still
 * listed and counted, but is excluded from the stock valuation.
 */
data class InventoryItem(
    val productId: String,
    val name: String,
    val sku: String,
    val units: Int,
    val reorderPoint: Int,
    val color: Color,
    val initials: String,
    val unitCost: Double? = null,
    /** InventoryRead.track_serials: the product is tracked unit-by-unit. */
    val trackSerials: Boolean = false,
    /**
     * The product's variants, each with its own balance.
     *
     * The API returns these with every row and this screen used to read none of them, so a product
     * sold in variants showed a figure the variants do not share - and nothing said so, which is
     * worse than showing nothing because the number looked like it meant something.
     */
    val variants: List<StockVariant> = emptyList(),
)

/** One variant of a stocked product, as the screen shows it. */
data class StockVariant(
    val variantId: String?,
    val name: String,
    val sku: String,
    val units: Int,
    val reorderPoint: Int,
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
) {
    val inventory = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    // Export hands the API's CSV to the system share sheet, which needs a Context and
    // somewhere for the chooser to be launched from.
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var filter by remember { mutableStateOf(StockFilter.All) }
    // The item an inventory dialog is open for; null while it is closed.
    var adjustTarget by remember { mutableStateOf<InventoryItem?>(null) }
    var receiveTarget by remember { mutableStateOf<InventoryItem?>(null) }
    // The variant the adjust dialog is for, when it was opened from a variant line rather than from
    // the row. Null means the product's own balance, which is what the row's own action changes.
    var adjustVariant by remember { mutableStateOf<StockVariant?>(null) }
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
                    .clickable(enabled = !viewModel.exporting) {
                        scope.launch {
                            viewModel.export { csv ->
                                shareCsv(context, "products.csv", csv, "Export products")
                            }
                        }
                    },
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

        if (viewModel.exportError != null) {
            Spacer(Modifier.height(10.dp))
            Text(
                viewModel.exportError.orEmpty(),
                color = ChmabaRed,
                fontSize = 11.5.sp,
                lineHeight = 16.sp,
            )
        }

        Spacer(Modifier.height(16.dp))

        // Σ(on_hand × cost_price) over the rows that carry a cost, matching
        // inventorySnapshot in apps/web/src/lib/dashboard.js. Rows with no cost
        // are excluded and disclosed rather than counted as zero.
        val priced = inventory.filter { it.unitCost != null }
        val stockValue = priced.sumOf { it.units * (it.unitCost ?: 0.0) }
        val unpriced = inventory.size - priced.size

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            MiniStat("Stock value", money(stockValue), ChmabaLavender, Modifier.weight(1f))
            MiniStat("Total units", inventory.sumOf { it.units }.toString(), LimeSoft, Modifier.weight(1f))
            MiniStat("Needs attention", needsAttention.toString(), YellowSoft, Modifier.weight(1f))
        }

        if (unpriced > 0) {
            Spacer(Modifier.height(8.dp))
            Text(
                if (unpriced == 1) {
                    "1 product has no cost recorded, so it is left out of the value."
                } else {
                    "$unpriced products have no cost recorded, so they are left out of the value."
                },
                color = ChmabaGray400,
                fontSize = 10.sp,
                lineHeight = 14.sp,
            )
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
                        .clickable {
                            // A row means the product, so a variant left over from a dialog that was
                            // dismissed must not travel with it: that would write the variant's
                            // balance while the row says it is changing the product's.
                            adjustVariant = null
                            adjustTarget = item
                        }
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
                        // A variant product's own balance is not the stock its variants hold, so the
                        // two are shown together rather than one being taken for the other.
                        if (item.variants.isNotEmpty()) {
                            Spacer(Modifier.height(3.dp))
                            item.variants.forEach { variant ->
                                Text(
                                    variant.name + " · " + variant.units + " units" +
                                        if (variant.units <= variant.reorderPoint) " · reorder" else "",
                                    color = ChmabaGray400,
                                    fontSize = 10.sp,
                                    // A variant's balance is the number worth correcting, so its own
                                    // line is the way into the dialog for it.
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            adjustTarget = item
                                            adjustVariant = variant
                                        }
                                        .padding(vertical = 2.dp),
                                )
                                Spacer(Modifier.height(1.dp))
                            }
                        }
                    }
                    ChmabaBadge(
                        text = "${item.units} units",
                        tone = levelOf(item),
                    )
                }
            }
            com.chmaba.pos.ui.components.LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading inventory…",
                failedTitle = "Could not load inventory",
                onRetry = { viewModel.load() },
            )
            if (visible.isEmpty() && viewModel.state is com.chmaba.pos.data.store.LoadState.Ready) {
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
                onClick = {
                    visible.firstOrNull()?.let {
                        adjustVariant = null
                        adjustTarget = it
                    }
                },
                text = "Adjust stock",
                modifier = Modifier.weight(1f),
                variant = ButtonVariant.Outline,
                size = ButtonSize.Large,
                enabled = visible.isNotEmpty(),
            )
            ChmabaButton(
                onClick = { visible.firstOrNull()?.let { receiveTarget = it } },
                text = "Receive stock",
                modifier = Modifier.weight(1f),
                variant = ButtonVariant.Primary,
                size = ButtonSize.Large,
                enabled = visible.isNotEmpty(),
            )
        }

        adjustTarget?.let { item ->
            StockDialog(
                title = "Adjust stock",
                // A variant's balance is its own, so the dialog names and counts the thing being
                // changed rather than the product it belongs to.
                blurb = adjustVariant?.let { item.name + " · " + it.name + " holds " + it.units + " now." }
                    ?: (item.name + " holds " + item.units + " now."),
                initial = (adjustVariant?.units ?: item.units).toString(),
                label = "New on-hand",
                saving = viewModel.saving,
                error = viewModel.error,
                onDismiss = {
                    viewModel.clearError()
                    adjustTarget = null
                    // Dismissing leaves no variant behind, so the state means one thing: a variant is
                    // in hand only while its dialog is open.
                    adjustVariant = null
                },
                onConfirm = { quantity ->
                    // The variant travels with the request: without it the API writes the product's
                    // own balance, which is not the number this dialog just showed.
                    viewModel.adjust(item.productId, quantity, adjustVariant?.variantId) {
                        adjustTarget = null
                        adjustVariant = null
                    }
                },
            )
        }

        receiveTarget?.let { item ->
            StockDialog(
                title = "Receive stock",
                blurb = item.name + " holds " + item.units + " now. How many arrived?",
                // The API adds this number, so the field starts empty rather than
                // prefilled with a running total.
                initial = "",
                label = "Quantity received",
                // Receiving nothing is not a receipt, so zero is not valid here.
                min = 1,
                saving = viewModel.saving,
                error = viewModel.error,
                onDismiss = {
                    viewModel.clearError()
                    receiveTarget = null
                },
                onConfirm = { quantity ->
                    viewModel.restock(item.productId, quantity) { receiveTarget = null }
                },
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
            // The API requires the serial numbers on a sale of a serial-tracked product, and
            // this app has no field to enter them. Saying the units are tracked here implied a
            // flow that does not exist.
            Text(
                "Serials are not captured in this app yet. The web POS records them on a sale; " +
                    "a serial-tracked product cannot be sold here.",
                color = ChmabaGray400,
                fontSize = 10.5.sp,
                lineHeight = 15.sp,
            )
            Spacer(Modifier.height(12.dp))
            // Real rows only: InventoryRead says which products track serials.
            // The serial numbers themselves come from another endpoint, so none
            // are shown here rather than inventing examples.
            val tracked = inventory.filter { it.trackSerials }
            if (tracked.isEmpty()) {
                Text("No products track serials at this store.", color = ChmabaGray400, fontSize = 10.5.sp)
            } else {
                tracked.take(3).forEachIndexed { index, item ->
                    if (index > 0) Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            item.name,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.weight(1f),
                        )
                        ChmabaBadge("${item.units} in stock", BadgeTone.Blue)
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

/**
 * Shared by Adjust and Receive. They differ only in what the number means — a new
 * total versus an added delta — so the wording and the minimum are passed in.
 */
@Composable
private fun StockDialog(
    title: String,
    blurb: String,
    initial: String,
    label: String,
    saving: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onConfirm: (Int) -> Unit,
    min: Int = 0,
) {
    var quantity by remember { mutableStateOf(initial) }
    val parsed = quantity.toIntOrNull()
    val valid = parsed != null && parsed >= min

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = ChmabaSurface,
        title = {
            Text(title, color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        },
        text = {
            Column {
                Text(
                    blurb,
                    color = ChmabaGray500,
                    fontSize = 11.5.sp,
                    lineHeight = 16.sp,
                )
                Spacer(Modifier.height(12.dp))
                ChmabaTextField(
                    value = quantity,
                    onValueChange = { quantity = it },
                    label = label,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
                if (error != null) {
                    Spacer(Modifier.height(10.dp))
                    Text(error, color = ChmabaRed, fontSize = 11.sp, lineHeight = 15.sp)
                }
            }
        },
        confirmButton = {
            ChmabaButton(
                onClick = { parsed?.let(onConfirm) },
                text = if (saving) "Saving…" else "Save",
                enabled = valid && !saving,
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
            )
        },
        dismissButton = {
            ChmabaButton(
                onClick = onDismiss,
                text = "Cancel",
                variant = ButtonVariant.Ghost,
                size = ButtonSize.Small,
            )
        },
    )
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
