package com.chmaba.pos.ui.screens.products

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
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray700
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaSurface

private val ProductsBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val YellowSoft = Color(0xFFFFF6DF)
private val LimeSoft = Color(0xFFEFF9E6)

/** Mirrors the web product list shape; placeholder data until the API is wired. */
data class Product(
    val id: String,
    val name: String,
    val sku: String,
    val category: String,
    val price: String,
    val stock: Int,
    val reorderPoint: Int,
    val color: Color,
    val initials: String,
    val isActive: Boolean = true,
)

private val SAMPLE_PRODUCTS = listOf(
    Product("1", "Iced Latte", "COF-001", "Coffee", "$4.50", 42, 10, Color(0xFFD7C0A2), "IL"),
    Product("2", "Matcha Cloud", "TEA-004", "Tea", "$5.25", 18, 10, Color(0xFFB9D7A2), "MC"),
    Product("3", "Butter Croissant", "BAK-002", "Bakery", "$3.20", 7, 10, Color(0xFFF0C986), "BC"),
    Product("4", "Chocolate Cookie", "BAK-008", "Bakery", "$2.40", 4, 10, Color(0xFFC99E83), "CC"),
    Product("5", "House Americano", "COF-002", "Coffee", "$3.50", 64, 10, Color(0xFFB79A83), "HA"),
)

/** Placeholder lookup by id until the products endpoint is wired.
 *  `null` or "new" means the editor is in add mode. */
fun sampleProduct(id: String?): Product? =
    if (id == null || id == "new") null else SAMPLE_PRODUCTS.firstOrNull { it.id == id }

private enum class StockLevel(val label: String, val tone: BadgeTone) {
    Healthy("In stock", BadgeTone.Green),
    Low("Low stock", BadgeTone.Yellow),
    Out("Out of stock", BadgeTone.Red),
}

private fun stockLevel(product: Product): StockLevel = when {
    product.stock <= 0 -> StockLevel.Out
    product.stock <= product.reorderPoint -> StockLevel.Low
    else -> StockLevel.Healthy
}

private val CATEGORY_FILTERS = listOf("All products", "Coffee", "Tea", "Bakery", "Cold drinks")

@Composable
fun ProductsScreen(
    modifier: Modifier = Modifier,
    viewModel: com.chmaba.pos.ui.screens.store.ProductsViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel(),
    onOpenProduct: (String) -> Unit = {},
    onAddProduct: () -> Unit = {},
) {
    val products = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    var category by remember { mutableStateOf("All products") }
    var query by remember { mutableStateOf("") }

    // Chips come from the loaded catalogue, not a fixed list, so they always
    // match what the store actually sells.
    val categories = remember(products) {
        listOf("All products") + products.map { it.category }.distinct().sorted()
    }

    val visible = products.filter { product ->
        (category == "All products" || product.category == category) &&
            (query.isBlank() ||
                product.name.contains(query, ignoreCase = true) ||
                product.sku.contains(query, ignoreCase = true))
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(ProductsBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Products",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text("Manage products and categories.", color = ChmabaGray500, fontSize = 12.5.sp)
            }
            ChmabaButton(
                onClick = onAddProduct,
                text = "Add",
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
                leadingIcon = {
                    Icon(ChmabaIcons.Plus, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                },
            )
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            MiniStat("Products", products.size.toString(), ChmabaLavender, Modifier.weight(1f))
            MiniStat("Active", products.count { it.isActive }.toString(), LimeSoft, Modifier.weight(1f))
            MiniStat(
                "Low stock",
                products.count { stockLevel(it) != StockLevel.Healthy }.toString(),
                YellowSoft,
                Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(14.dp))

        ChmabaTextField(
            value = query,
            onValueChange = { query = it },
            label = "Search",
            placeholder = "Search by name or SKU…",
        )

        Spacer(Modifier.height(6.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            categories.forEach { entry ->
                val active = entry == category
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(9.dp))
                        .background(if (active) ChmabaBlue else ChmabaSurface)
                        .clickable { category = entry }
                        .padding(horizontal = 12.dp, vertical = 7.dp),
                ) {
                    Text(
                        entry,
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
            visible.forEachIndexed { index, product ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpenProduct(product.id) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    ProductMark(product)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            product.name,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "${product.sku} · ${product.category}",
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            product.price,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.ExtraBold,
                        )
                        Spacer(Modifier.height(3.dp))
                        val level = stockLevel(product)
                        ChmabaBadge(
                            text = if (level == StockLevel.Healthy) level.label else "${level.label} · ${product.stock}",
                            tone = level.tone,
                        )
                    }
                }
            }
            if (visible.isEmpty()) {
                Text(
                    "No products match this filter.",
                    color = ChmabaGray400,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(20.dp),
                )
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun ProductMark(product: Product) {
    Box(
        modifier = Modifier
            .size(36.dp)
            .clip(RoundedCornerShape(11.dp))
            .background(product.color),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            product.initials,
            color = Color(0xFF343039),
            fontSize = 11.sp,
            fontWeight = FontWeight.ExtraBold,
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

/**
 * Product editor. Mirrors the web's product form: identity, pricing, category,
 * image, stock rules and the two tracking switches (inventory / serials).
 */
@Composable
fun ProductEditorScreen(
    modifier: Modifier = Modifier,
    product: Product? = SAMPLE_PRODUCTS.first(),
    onBack: () -> Unit = {},
    onSave: (name: String, sku: String, price: String) -> Unit = { _, _, _ -> },
) {
    val isEdit = product != null

    var name by remember { mutableStateOf(product?.name ?: "") }
    var sku by remember { mutableStateOf(product?.sku ?: "") }
    var price by remember { mutableStateOf(product?.price?.removePrefix("$") ?: "") }
    var costPrice by remember { mutableStateOf("") }
    var taxRate by remember { mutableStateOf("") }
    var barcode by remember { mutableStateOf("") }
    var brand by remember { mutableStateOf("") }
    var category by remember { mutableStateOf(product?.category ?: "Coffee") }
    var description by remember { mutableStateOf("") }
    var stock by remember { mutableStateOf(product?.stock?.toString() ?: "0") }
    var reorderPoint by remember { mutableStateOf(product?.reorderPoint?.toString() ?: "10") }
    var trackInventory by remember { mutableStateOf(true) }
    var trackSerials by remember { mutableStateOf(false) }

    val canSave = name.isNotBlank() && sku.isNotBlank() && price.toDoubleOrNull() != null

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(ProductsBg)
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
                    if (isEdit) "Edit ${product?.name}" else "Add product",
                    color = ChmabaGray900,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    if (isEdit) "Update product details and image." else "Add a new product to your catalog.",
                    color = ChmabaGray500,
                    fontSize = 11.sp,
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = "Name",
                    placeholder = "e.g. Iced Latte",
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                )
            }
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = sku,
                    onValueChange = { sku = it },
                    label = "SKU",
                    placeholder = "COF-001",
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = price,
                    onValueChange = { price = it },
                    label = "Price",
                    placeholder = "0.00",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Next),
                )
            }
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = costPrice,
                    onValueChange = { costPrice = it },
                    label = "Cost price",
                    placeholder = "0.00",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Next),
                )
            }
        }

        ChmabaTextField(
            value = taxRate,
            onValueChange = { taxRate = it },
            label = "Tax rate %",
            placeholder = "Store default",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Next),
        )

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = barcode,
                    onValueChange = { barcode = it },
                    label = "Barcode",
                    placeholder = "Scan or type",
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                )
            }
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = brand,
                    onValueChange = { brand = it },
                    label = "Brand",
                    placeholder = "e.g. Apple",
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                )
            }
        }

        ChmabaTextField(
            value = category,
            onValueChange = { category = it },
            label = "Category",
            placeholder = "Coffee",
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(ChmabaSurface)
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(11.dp))
                    .background(product?.color ?: ChmabaLavender),
                contentAlignment = Alignment.Center,
            ) {
                if (product != null) {
                    Text(product.initials, color = Color(0xFF343039), fontSize = 12.sp, fontWeight = FontWeight.ExtraBold)
                } else {
                    Icon(ChmabaIcons.Image, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(20.dp))
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("Upload product image", color = ChmabaBlue, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(2.dp))
                Text("or choose from library", color = ChmabaGray400, fontSize = 10.sp)
            }
        }

        Spacer(Modifier.height(14.dp))

        ChmabaTextField(
            value = description,
            onValueChange = { description = it },
            label = "Description",
            placeholder = "Optional",
            singleLine = false,
            maxLines = 3,
        )

        // Variants use the same "add later" affordance as the web form.
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(ChmabaSurface)
                .padding(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Variants", color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                Text("Add", color = ChmabaBlue, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "Sell one product in several combinations, each with its own stock.",
                color = ChmabaGray400,
                fontSize = 10.5.sp,
                lineHeight = 15.sp,
            )
        }

        Spacer(Modifier.height(14.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = stock,
                    onValueChange = { stock = it },
                    label = "In stock",
                    enabled = product == null,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Next),
                )
            }
            Box(Modifier.weight(1f)) {
                ChmabaTextField(
                    value = reorderPoint,
                    onValueChange = { reorderPoint = it },
                    label = "Reorder point",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
            }
        }

        CheckRow("Track inventory", trackInventory) { trackInventory = it }
        CheckRow("Track serials / IMEI", trackSerials) { trackSerials = it }

        Spacer(Modifier.height(6.dp))

        ChmabaButton(
            onClick = { onSave(name, sku, price) },
            text = if (isEdit) "Save product" else "Add product",
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = canSave,
            trailingIcon = {
                Icon(ChmabaIcons.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
            },
        )
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun CheckRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onChange,
            colors = CheckboxDefaults.colors(checkedColor = ChmabaBlue, uncheckedColor = ChmabaGray400),
            modifier = Modifier.size(22.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(label, color = ChmabaGray700, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
    }
}
