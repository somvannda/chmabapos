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
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.data.catalog.ProductWriteBody
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import kotlinx.coroutines.delay
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
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface

private val ProductsBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val YellowSoft = Color(0xFFFFF6DF)
private val LimeSoft = Color(0xFFEFF9E6)

/** A category the store already has; the editor resolves a typed name to its id. */
data class CategoryOption(val id: String, val name: String)

/**
 * One row of the catalogue. It also carries the editable fields, so the editor
 * can prefill every input from the real product instead of starting blank.
 */
/** One variant row in the editor. A null [id] means it is new and has no server row yet. */
data class ProductVariant(
    val id: String? = null,
    val name: String = "",
    val sku: String = "",
    val price: String = "",
)

data class Product(
    val id: String,
    val name: String,
    val sku: String,
    /**
     * The category's name, or null when the product has none. It stays null rather
     * than becoming an "Uncategorised" label here, because the editor validates a
     * typed name against the store's real categories - a placeholder would be read
     * as a typed value and block the save. Screens that only display it fall back
     * to [UNCATEGORISED] themselves.
     */
    val category: String? = null,
    /** The price for display: it carries the store's currency sign. */
    val price: String,
    /**
     * The same price as the server states it, unformatted. The editor seeds its field from this
     * rather than from [price], whose currency sign cannot be stripped: doing so with a
     * hardcoded "$" stopped working the moment `money()` learned to render baht and riel, and
     * the editor would then have saved "฿12.00" as a price.
     */
    val rawPrice: String = "",
    val stock: Int,
    val reorderPoint: Int,
    val color: Color,
    val initials: String,
    val isActive: Boolean = true,
    val costPrice: String = "",
    val taxRate: String = "",
    val barcode: String = "",
    val brand: String = "",
    val description: String = "",
    val trackInventory: Boolean = true,
    val trackSerials: Boolean = false,
    val variants: List<ProductVariant> = emptyList(),
)

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

/** Shown wherever a product has no category, so the label is defined once. */
private const val UNCATEGORISED = "Uncategorised"

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
        listOf("All products") + products.mapNotNull { it.category }.distinct().sorted()
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
                            "${product.sku} · ${product.category ?: UNCATEGORISED}",
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
            com.chmaba.pos.ui.components.LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading products…",
                failedTitle = "Could not load products",
                onRetry = { viewModel.load() },
            )
            if (visible.isEmpty() && viewModel.state is com.chmaba.pos.data.store.LoadState.Ready) {
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
    /** The product being edited, or null for "add". Never a sample default. */
    product: Product? = null,
    saving: Boolean = false,
    error: String? = null,
    onBack: () -> Unit = {},
    /** Categories the store already has, so a typed name can resolve to an id. */
    categoryOptions: List<CategoryOption> = emptyList(),
    savingVariants: Boolean = false,
    variantsError: String? = null,
    /** True just after a successful variants save, so the card can say so. */
    variantsSaved: Boolean = false,
    /** Called once the confirmation has been shown, so it does not linger. */
    onVariantsSavedShown: () -> Unit = {},
    onSaveVariants: (List<ProductVariant>) -> Unit = {},
    onSave: (ProductWriteBody) -> Unit = {},
) {
    val isEdit = product != null

    var name by remember { mutableStateOf(product?.name ?: "") }
    var sku by remember { mutableStateOf(product?.sku ?: "") }
    // From the raw price, never the display string, which carries the store's currency sign.
    var price by remember { mutableStateOf(product?.rawPrice ?: "") }
    var costPrice by remember { mutableStateOf(product?.costPrice ?: "") }
    var taxRate by remember { mutableStateOf(product?.taxRate ?: "") }
    var barcode by remember { mutableStateOf(product?.barcode ?: "") }
    var brand by remember { mutableStateOf(product?.brand ?: "") }
    // Not defaulted to a category: an unset category must stay unset.
    var category by remember { mutableStateOf(product?.category ?: "") }
    var description by remember { mutableStateOf(product?.description ?: "") }
    var stock by remember { mutableStateOf(product?.stock?.toString() ?: "0") }
    var reorderPoint by remember { mutableStateOf(product?.reorderPoint?.toString() ?: "10") }
    var trackInventory by remember { mutableStateOf(product?.trackInventory ?: true) }
    var trackSerials by remember { mutableStateOf(product?.trackSerials ?: false) }
    // The variant rows, prefilled from the product. Saving replaces the whole set,
    // which is what the API's PUT means. Keyed on the product's own variants so a save
    // adopts the ids the server assigned: otherwise a row added here would still have no
    // id afterwards, and saving twice would create it twice instead of updating it.
    var variants by remember(product?.variants) {
        mutableStateOf(product?.variants ?: emptyList())
    }

    // The API requires price > 0, so zero must not pass the client check either.
    val priceValue = price.toDoubleOrNull()
    // A typed category has to match one the store already has: the request only
    // carries a category id, so an unmatched name could not be sent and the
    // change would silently do nothing.
    val matchedCategory = categoryOptions.firstOrNull { it.name.equals(category.trim(), ignoreCase = true) }
    val categoryUnmatched = category.isNotBlank() && matchedCategory == null
    val canSave = name.isNotBlank() && sku.isNotBlank() && priceValue != null &&
        priceValue > 0.0 && !categoryUnmatched

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
            // An example from the store's own categories, because a typed name has to
            // match one of them exactly. A fixed example would name a category the
            // store may not have.
            placeholder = categoryOptions.firstOrNull()?.let { "e.g. " + it.name } ?: "No categories yet",
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

        // Variants. The API's PUT replaces the whole set, so this edits the list and
        // saves it as a unit rather than one row at a time. A row keeps its id so an
        // existing variant is updated; a row left out is removed.
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
                if (isEdit) {
                    Text(
                        "Add",
                        color = ChmabaBlue,
                        fontSize = 11.5.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier
                            .padding(4.dp)
                            .clickable { variants = variants + ProductVariant() },
                    )
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                if (isEdit) {
                    "Sell one product in several combinations. Saving replaces the whole list."
                } else {
                    "Save the product first, then add variants to it."
                },
                color = ChmabaGray400,
                fontSize = 10.5.sp,
                lineHeight = 15.sp,
            )

            if (isEdit && variants.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                variants.forEachIndexed { index, row ->
                    if (index > 0) Spacer(Modifier.height(12.dp))
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                if (row.id == null) "New variant" else "Variant",
                                color = ChmabaGray500,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                "Remove",
                                color = ChmabaRed,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier
                                    .padding(4.dp)
                                    .clickable {
                                        variants = variants.filterIndexed { i, _ -> i != index }
                                    },
                            )
                        }
                        Spacer(Modifier.height(6.dp))
                        ChmabaTextField(
                            value = row.name,
                            onValueChange = { text ->
                                variants = variants.mapIndexed { i, line ->
                                    if (i == index) line.copy(name = text) else line
                                }
                            },
                            label = "Variant name",
                            placeholder = "e.g. Large",
                        )
                        Spacer(Modifier.height(6.dp))
                        ChmabaTextField(
                            value = row.sku,
                            onValueChange = { text ->
                                variants = variants.mapIndexed { i, line ->
                                    if (i == index) line.copy(sku = text) else line
                                }
                            },
                            label = "Variant SKU",
                            placeholder = "e.g. COF-001-L",
                        )
                        Spacer(Modifier.height(6.dp))
                        ChmabaTextField(
                            value = row.price,
                            onValueChange = { text ->
                                variants = variants.mapIndexed { i, line ->
                                    if (i == index) line.copy(price = text) else line
                                }
                            },
                            label = "Variant price",
                            placeholder = "Optional",
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
            }

            // Kept out of the block above on purpose: removing the last row empties
            // [variants], and the button has to survive that, or the removal could never
            // be saved. An empty list is exactly what the PUT needs to clear the set.
            if (isEdit && (variants.isNotEmpty() || !product?.variants.isNullOrEmpty())) {
                Spacer(Modifier.height(12.dp))
                ChmabaButton(
                    onClick = { onSaveVariants(variants) },
                    text = if (savingVariants) "Saving…" else "Save variants",
                    modifier = Modifier.fillMaxWidth(),
                    variant = ButtonVariant.Outline,
                    enabled = !savingVariants &&
                        variants.all { it.name.isNotBlank() && it.sku.isNotBlank() },
                )
            }

            if (variantsSaved) {
                Spacer(Modifier.height(10.dp))
                Text(
                    "Variants saved.",
                    color = com.chmaba.pos.ui.theme.ChmabaGreen,
                    fontSize = 11.sp,
                    lineHeight = 15.sp,
                )
                // Says so once, then gets out of the way.
                LaunchedEffect(Unit) {
                    delay(3000)
                    onVariantsSavedShown()
                }
                // And if the editor is left before that timer fires, clear it on the way
                // out, so the next visit does not open on a stale confirmation.
                DisposableEffect(Unit) { onDispose { onVariantsSavedShown() } }
            }

            if (variantsError != null) {
                Spacer(Modifier.height(10.dp))
                Text(variantsError, color = ChmabaRed, fontSize = 11.sp, lineHeight = 15.sp)
            }
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
            onClick = {
                onSave(
                    ProductWriteBody(
                        name = name.trim(),
                        sku = sku.trim(),
                        price = price.trim(),
                        costPrice = costPrice.trim().ifBlank { null },
                        taxRate = taxRate.trim().ifBlank { null },
                        categoryId = matchedCategory?.id,
                        description = description.trim().ifBlank { null },
                        barcode = barcode.trim().ifBlank { null },
                        brand = brand.trim().ifBlank { null },
                        trackInventory = trackInventory,
                        trackSerials = trackSerials,
                        // opening_stock and reorder_point exist only on create,
                        // so they stay null when updating.
                        openingStock = if (isEdit) null else stock.trim().ifBlank { "0" },
                        reorderPoint = if (isEdit) null else reorderPoint.trim().toIntOrNull(),
                    ),
                )
            },
            text = when {
                saving -> "Saving…"
                isEdit -> "Save product"
                else -> "Add product"
            },
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = canSave && !saving,
            trailingIcon = {
                Icon(ChmabaIcons.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
            },
        )
        // Surface either the server's failure or the reason Save is disabled.
        val problem = error ?: if (categoryUnmatched) {
            "That category is not one of this store's, so it cannot be saved. Known: " +
                categoryOptions.joinToString(", ") { it.name }
        } else {
            null
        }
        if (problem != null) {
            Spacer(Modifier.height(10.dp))
            Text(problem, color = ChmabaRed, fontSize = 11.5.sp, lineHeight = 16.sp)
        }
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
