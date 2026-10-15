package com.chmaba.pos.ui.screens.pos

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.rememberBarcodeScannerLauncher
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.screens.customers.Customer
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray300
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray700
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaGreen
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaLime
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface
import java.util.Locale

private val PosBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val InkDark = Color(0xFF17181C)
private val SoftPanel = Color(0xFFFAFAFD)
private val GreenSoft = Color(0xFFEFF9E6)
private val GreenInk = Color(0xFF4F8B32)
/**
 * A rate written the way it is spoken: "10.00" reads "10", "7.50" reads "7.5". Trimmed
 * by hand, because trimEnd('0') would turn "10.00" into "1".
 */
private fun rateLabel(rate: String): String {
    val parts = rate.trim().split(".")
    val whole = parts[0].ifBlank { "0" }
    val fraction = parts.getOrNull(1).orEmpty().trimEnd('0')
    return if (fraction.isEmpty()) whole else whole + "." + fraction
}

private fun money(value: Double): String = "$" + String.format(Locale.US, "%.2f", value)

/** Money is only ever whole cents. Without this the true total keeps sub-cent
 *  precision (e.g. 5.6925) while the screen shows 5.69, so "Exact" cash would
 *  never satisfy the total and the sale could not be completed. */
private fun round2(value: Double): Double = Math.round(value * 100.0) / 100.0

// ---------------------------------------------------------------- models

data class ModifierOption(val id: String, val name: String, val priceDelta: Double = 0.0)
data class ModifierGroup(val name: String, val options: List<ModifierOption>, val required: Boolean = false)
data class SelectedModifier(val optionId: String, val name: String, val priceDelta: Double)

data class PosProduct(
    val id: String,
    val name: String,
    val sku: String,
    val category: String,
    val price: Double,
    val stock: Int,
    val color: Color,
    val initials: String,
    /** The product's barcode, so the scanner can match one. Null when none is stored. */
    val barcode: String? = null,
    val modifierGroups: List<ModifierGroup> = emptyList(),
)

data class CartLine(
    val product: PosProduct,
    val quantity: Int,
    val modifiers: List<SelectedModifier> = emptyList(),
) {
    val unitPrice: Double get() = product.price + modifiers.sumOf { it.priceDelta }
    val lineTotal: Double get() = unitPrice * quantity
    /** Distinct lines: same product with different options is a different line. */
    val key: String get() = product.id + "#" + modifiers.map { it.optionId }.sorted().joinToString("|")
}

data class HeldOrder(val id: String, val label: String, val lines: List<CartLine>, val itemCount: Int)

private enum class Tender(val label: String, val method: String) {
    Cash("Cash", "cash"),
    Khqr("KHQR", "khqr"),
}

private enum class DiscountMode(val label: String) { None("None"), Percent("Percent"), Flat("Amount") }

// ---------------------------------------------------------------- screen

/**
 * Mobile-first point of sale.
 *
 * The desktop web layout is three columns with a fixed cart sidebar, which
 * cannot work on a ~400dp phone. Here the grid owns the full width, the cart is
 * a persistent bottom bar that opens a sheet, and every secondary flow
 * (modifiers, discount, customer, held orders, scan, payment) is a bottom sheet
 * so the product grid is never displaced.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun POSScreen(
    modifier: Modifier = Modifier,
    viewModel: PosViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
    /** Real customers for the attach-customer sheet; supplied by the shell. */
    customers: List<Customer> = emptyList(),
) {
    var query by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("All items") }
    var cart by remember { mutableStateOf<List<CartLine>>(emptyList()) }
    var heldOrders by remember { mutableStateOf<List<HeldOrder>>(emptyList()) }

    var discountMode by remember { mutableStateOf(DiscountMode.None) }
    var discountValue by remember { mutableStateOf("") }
    var customer by remember { mutableStateOf<String?>(null) }

    var cartOpen by remember { mutableStateOf(false) }
    var paymentOpen by remember { mutableStateOf(false) }
    var modifierFor by remember { mutableStateOf<PosProduct?>(null) }
    var discountOpen by remember { mutableStateOf(false) }
    var customerOpen by remember { mutableStateOf(false) }
    var heldOpen by remember { mutableStateOf(false) }
    var scanOpen by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }

    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    val loaded = (viewModel.productsState as? ProductsState.Ready)?.products.orEmpty()
    val categories = remember(loaded) {
        listOf("All items") + loaded.map { it.category }.distinct().sorted()
    }
    val visible = loaded.filter { product ->
        (category == "All items" || product.category == category) &&
            (query.isBlank() ||
                product.name.contains(query, ignoreCase = true) ||
                product.sku.contains(query, ignoreCase = true))
    }

    val itemCount = cart.sumOf { it.quantity }
    val subtotal = round2(cart.sumOf { it.lineTotal })
    val discountAmount = round2(
        when (discountMode) {
            DiscountMode.None -> 0.0
            DiscountMode.Percent -> subtotal * ((discountValue.toDoubleOrNull() ?: 0.0) / 100.0)
            DiscountMode.Flat -> discountValue.toDoubleOrNull() ?: 0.0
        }.coerceIn(0.0, subtotal),
    )
    val taxable = round2(subtotal - discountAmount)
    // The store's own rate, from its StoreRead. A fixed 10% was only right for a store
    // that had never changed the default, and this total is what "Exact" cash tenders,
    // so any other rate short-tendered the sale against what the server would charge.
    val taxRate = com.chmaba.pos.data.orders.Session.serviceTaxRate.toDoubleOrNull() ?: 10.0
    val tax = round2(taxable * (taxRate / 100.0))
    val total = round2(taxable + tax)

    fun quantityOf(key: String) = cart.firstOrNull { it.key == key }?.quantity ?: 0

    fun addLine(product: PosProduct, modifiers: List<SelectedModifier>) {
        val key = product.id + "#" + modifiers.map { it.optionId }.sorted().joinToString("|")
        val current = quantityOf(key)
        if (current >= product.stock) {
            notice = "Only ${product.stock} of ${product.name} in stock"
            return
        }
        cart = if (current > 0) {
            cart.map { if (it.key == key) it.copy(quantity = it.quantity + 1) else it }
        } else {
            cart + CartLine(product, 1, modifiers)
        }
    }

    fun tapProduct(product: PosProduct) {
        if (product.stock <= 0) {
            notice = "${product.name} is out of stock"
            return
        }
        if (product.modifierGroups.isEmpty()) addLine(product, emptyList()) else modifierFor = product
    }

    fun resetOrder() {
        cart = emptyList()
        customer = null
        discountMode = DiscountMode.None
        discountValue = ""
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = PosBg,
        topBar = {
            PosHeader(
                heldCount = heldOrders.size,
                onScan = { scanOpen = true },
                onHold = {
                    if (cart.isNotEmpty()) {
                        val label = "Held ${heldOrders.size + 1}"
                        heldOrders = heldOrders + HeldOrder(
                            id = label,
                            label = label,
                            lines = cart,
                            itemCount = itemCount,
                        )
                        resetOrder()
                        notice = "Order parked — resume it from Held"
                    }
                },
                onOpenHeld = { heldOpen = true },
            )
        },
        bottomBar = {
            // The customer sheet used to be reachable only from inside the cart,
            // so with an empty cart — or a store with nothing in stock — there
            // was no way to attach a customer at all.
            if (cart.isNotEmpty()) {
                CartBar(itemCount = itemCount, total = total, onOpenCart = { cartOpen = true })
            } else {
                EmptyCartBar(customer = customer, onCustomer = { customerOpen = true })
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            SearchRow(query, { query = it }, onScan = { scanOpen = true })
            CategoryRow(categories, category) { category = it }

            notice?.let { message ->
                NoticeBanner(message) { notice = null }
            }

            when (val state = viewModel.productsState) {
                is ProductsState.Loading -> ProductsLoading()

                is ProductsState.Error -> ProductsError(state.message) { viewModel.loadProducts() }

                is ProductsState.Ready ->
                    if (visible.isEmpty()) {
                        EmptyProducts()
                    } else {
                        LazyVerticalGrid(
                            columns = GridCells.Fixed(2),
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 20.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            items(visible, key = { it.id }) { product ->
                                ProductTile(
                                    product = product,
                                    inCart = cart.filter { it.product.id == product.id }.sumOf { it.quantity },
                                ) { tapProduct(product) }
                            }
                        }
                    }
            }
        }
    }

    // ---- sheets -------------------------------------------------------

    modifierFor?.let { product ->
        ModalBottomSheet(onDismissRequest = { modifierFor = null }, sheetState = sheetState, containerColor = ChmabaSurface) {
            ModifierSheet(
                product = product,
                onAdd = { modifiers ->
                    addLine(product, modifiers)
                    modifierFor = null
                },
            )
        }
    }

    if (cartOpen) {
        ModalBottomSheet(onDismissRequest = { cartOpen = false }, sheetState = sheetState, containerColor = ChmabaSurface) {
            CartSheet(
                cart = cart,
                customer = customer,
                discountLabel = when {
                    discountMode == DiscountMode.None -> null
                    discountMode == DiscountMode.Percent -> "-${discountValue.ifBlank { "0" }}%"
                    else -> "-${money(discountAmount)}"
                },
                subtotal = subtotal,
                discount = discountAmount,
                tax = tax,
                total = total,
                onChangeQuantity = { key, qty ->
                    cart = if (qty <= 0) cart.filterNot { it.key == key }
                    else cart.map { if (it.key == key) it.copy(quantity = qty.coerceAtMost(it.product.stock)) else it }
                },
                onClear = { resetOrder(); cartOpen = false },
                onDiscount = { cartOpen = false; discountOpen = true },
                onCustomer = { cartOpen = false; customerOpen = true },
                onCharge = { cartOpen = false; paymentOpen = true },
            )
        }
    }

    if (discountOpen) {
        ModalBottomSheet(onDismissRequest = { discountOpen = false }, sheetState = sheetState, containerColor = ChmabaSurface) {
            DiscountSheet(
                mode = discountMode,
                value = discountValue,
                subtotal = subtotal,
                onApply = { nextMode, nextValue ->
                    val parsed = nextValue.toDoubleOrNull() ?: 0.0
                    // A blank or zero entry clears the discount rather than showing "-0%".
                    val effective =
                        if (nextMode == DiscountMode.None || parsed <= 0.0) DiscountMode.None else nextMode
                    discountMode = effective
                    discountValue = if (effective == DiscountMode.None) "" else nextValue
                    discountOpen = false
                    cartOpen = true
                },
            )
        }
    }

    if (customerOpen) {
        ModalBottomSheet(onDismissRequest = { customerOpen = false }, sheetState = sheetState, containerColor = ChmabaSurface) {
            CustomerSheet(
                selected = customer,
                customers = customers,
                onPick = { name ->
                    customer = name
                    customerOpen = false
                    cartOpen = true
                },
            )
        }
    }

    if (heldOpen) {
        ModalBottomSheet(onDismissRequest = { heldOpen = false }, sheetState = sheetState, containerColor = ChmabaSurface) {
            HeldOrdersSheet(
                held = heldOrders,
                onResume = { held ->
                    cart = held.lines
                    heldOrders = heldOrders.filterNot { it.id == held.id }
                    heldOpen = false
                    cartOpen = true
                },
                onDiscard = { held -> heldOrders = heldOrders.filterNot { it.id == held.id } },
            )
        }
    }

    if (scanOpen) {
        ModalBottomSheet(onDismissRequest = { scanOpen = false }, sheetState = sheetState, containerColor = ChmabaSurface) {
            ScanSheet(
                onScanned = { code ->
                    // The store's real catalogue. A scanned code arrives as a barcode,
                    // and one typed by hand is usually the SKU or the name, so all three
                    // identifiers are tried. This used to look in an invented product
                    // list, which put products the server does not have into the cart and
                    // refused the store's real ones.
                    val match = loaded.firstOrNull {
                        it.sku.equals(code, ignoreCase = true) ||
                            it.name.equals(code, ignoreCase = true) ||
                            it.barcode.equals(code, ignoreCase = true)
                    }
                    if (match == null) {
                        notice = "Nothing matches \"$code\""
                    } else {
                        tapProduct(match)
                    }
                    scanOpen = false
                },
            )
        }
    }

    if (paymentOpen) {
        ModalBottomSheet(onDismissRequest = { paymentOpen = false }, sheetState = sheetState, containerColor = ChmabaSurface) {
            PaymentSheet(
                total = total,
                onComplete = { tender ->
                    paymentOpen = false
                    viewModel.submit(
                        lines = cart,
                        method = tender.method,
                        discount = discountAmount,
                        customer = customer,
                        total = total,
                    )
                },
                onBack = { paymentOpen = false; cartOpen = true },
            )
        }
    }

    if (viewModel.submitting) {
        ModalBottomSheet(
            onDismissRequest = { },
            sheetState = sheetState,
            containerColor = ChmabaSurface,
        ) {
            SendingSheet()
        }
    }

    viewModel.error?.let { message ->
        ModalBottomSheet(
            onDismissRequest = { viewModel.clear() },
            sheetState = sheetState,
            containerColor = ChmabaSurface,
        ) {
            SaleErrorSheet(
                message = message,
                onRetry = { viewModel.clear(); paymentOpen = true },
                onBackToCart = { viewModel.clear(); cartOpen = true },
            )
        }
    }

    viewModel.outcome?.let { sale ->
        ModalBottomSheet(
            onDismissRequest = { viewModel.clear(); resetOrder() },
            sheetState = sheetState,
            containerColor = ChmabaSurface,
        ) {
            SuccessSheet(
                orderNumber = sale.orderNumber,
                total = sale.total,
                onDone = { viewModel.clear(); resetOrder() },
            )
        }
    }
}

// ---------------------------------------------------------------- chrome

@Composable
private fun PosHeader(
    heldCount: Int,
    onScan: () -> Unit,
    onHold: () -> Unit,
    onOpenHeld: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(PosBg)
            .padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
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
                    // This app has no register or shift concept, so it must not name a
                    // register. The store the sale will land in is real, and is the
                    // useful thing to show here.
                    com.chmaba.pos.data.orders.Session.storeName ?: "This till",
                    color = ChmabaGray500,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Spacer(Modifier.height(3.dp))
            Text(
                "Make a sale",
                color = ChmabaGray900,
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.05).sp,
            )
        }
        SquareIconButton(ChmabaIcons.Scan, "Scan item", onScan)
        Spacer(Modifier.width(8.dp))
        SquareIconButton(ChmabaIcons.Archive, "Hold order", onHold)
        Spacer(Modifier.width(8.dp))
        SquareIconButton(
            icon = ChmabaIcons.Receipt,
            label = if (heldCount > 0) "Held orders ($heldCount)" else "Held orders",
            onClick = onOpenHeld,
            badge = heldCount,
        )
    }
}

@Composable
private fun SquareIconButton(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit,
    badge: Int = 0,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.9f else 1f, tween(120), label = "sq-press")
    Box(
        modifier = Modifier
            .size(42.dp)
            .graphicsLayer { scaleX = scale; scaleY = scale }
            .clip(RoundedCornerShape(13.dp))
            .background(ChmabaSurface)
            .clickable(interactionSource = interaction, indication = null, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = label, tint = ChmabaGray700, modifier = Modifier.size(19.dp))
        if (badge > 0) {
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(3.dp)
                    .size(16.dp)
                    .clip(CircleShape)
                    .background(ChmabaBlue),
                contentAlignment = Alignment.Center,
            ) {
                Text("$badge", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.ExtraBold)
            }
        }
    }
}

@Composable
private fun NoticeBanner(message: String, onDismiss: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
            .padding(bottom = 8.dp)
            .clip(RoundedCornerShape(13.dp))
            .background(Color(0xFFFFF6DF))
            .clickable(onClick = onDismiss)
            .padding(horizontal = 14.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(ChmabaIcons.Alert, contentDescription = null, tint = Color(0xFFAD7D1C), modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(10.dp))
        Text(message, color = Color(0xFFAD7D1C), fontSize = 11.5.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
        Text("Dismiss", color = Color(0xFFAD7D1C), fontSize = 10.5.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun SearchRow(query: String, onQueryChange: (String) -> Unit, onScan: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier
                .weight(1f)
                .height(52.dp),
            placeholder = { Text("Search or scan a product…", color = ChmabaGray400, fontSize = 13.sp) },
            leadingIcon = {
                Icon(ChmabaIcons.Search, contentDescription = null, tint = ChmabaGray400, modifier = Modifier.size(18.dp))
            },
            trailingIcon = {
                Box(
                    modifier = Modifier
                        .padding(end = 6.dp)
                        .size(34.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(ChmabaLavender)
                        .clickable(onClick = onScan),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(ChmabaIcons.Camera, contentDescription = "Scan", tint = ChmabaBlue, modifier = Modifier.size(17.dp))
                }
            },
            singleLine = true,
            shape = RoundedCornerShape(14.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = ChmabaBlue,
                unfocusedBorderColor = ChmabaGray300,
                focusedContainerColor = ChmabaSurface,
                unfocusedContainerColor = ChmabaSurface,
                cursorColor = ChmabaBlue,
            ),
        )
    }
}

@Composable
private fun CategoryRow(categories: List<String>, selected: String, onSelect: (String) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        categories.forEach { entry ->
            val active = entry == selected
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(99.dp))
                    .background(if (active) ChmabaBlue else ChmabaSurface)
                    .clickable { onSelect(entry) }
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            ) {
                Text(
                    entry,
                    color = if (active) Color.White else ChmabaGray500,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun EmptyProducts() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(ChmabaIcons.Search, contentDescription = null, tint = ChmabaGray300, modifier = Modifier.size(30.dp))
        Spacer(Modifier.height(10.dp))
        Text("No products match", color = ChmabaGray500, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text("Try another search or category.", color = ChmabaGray400, fontSize = 11.5.sp)
    }
}

@Composable
private fun ProductsLoading() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        androidx.compose.material3.CircularProgressIndicator(
            color = ChmabaBlue,
            strokeWidth = 3.dp,
            modifier = Modifier.size(30.dp),
        )
        Spacer(Modifier.height(12.dp))
        Text("Loading products…", color = ChmabaGray500, fontSize = 12.5.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun ProductsError(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(46.dp)
                .clip(RoundedCornerShape(15.dp))
                .background(Color(0xFFFFF0EE)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(ChmabaIcons.Alert, contentDescription = null, tint = ChmabaRed, modifier = Modifier.size(22.dp))
        }
        Spacer(Modifier.height(14.dp))
        Text("Could not load products", color = ChmabaGray900, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(6.dp))
        Text(
            message,
            color = ChmabaGray500,
            fontSize = 11.5.sp,
            textAlign = TextAlign.Center,
            lineHeight = 17.sp,
        )
        Spacer(Modifier.height(16.dp))
        QuickChip("Try again", onRetry)
    }
}

@Composable
private fun ProductTile(product: PosProduct, inCart: Int, onTap: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.96f else 1f, tween(110), label = "tile-press")
    val low = product.stock in 1..10

    Column(
        modifier = Modifier
            .graphicsLayer { scaleX = scale; scaleY = scale }
            .clip(RoundedCornerShape(16.dp))
            .background(ChmabaSurface)
            .clickable(interactionSource = interaction, indication = null, onClick = onTap),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(72.dp)
                .background(product.color),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                product.initials,
                color = Color(0xFF343039),
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.04).sp,
            )
            if (low) {
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(6.dp)
                        .clip(RoundedCornerShape(99.dp))
                        .background(Color(0xFFFFF6DF))
                        .padding(horizontal = 6.dp, vertical = 2.dp),
                ) {
                    Text("${product.stock} left", color = Color(0xFFAD7D1C), fontSize = 8.5.sp, fontWeight = FontWeight.Bold)
                }
            }
            if (product.modifierGroups.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(6.dp)
                        .clip(RoundedCornerShape(99.dp))
                        .background(Color.White.copy(alpha = 0.85f))
                        .padding(horizontal = 6.dp, vertical = 2.dp),
                ) {
                    Text("Options", color = ChmabaGray700, fontSize = 8.5.sp, fontWeight = FontWeight.Bold)
                }
            }
            if (inCart > 0) {
                Box(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(6.dp)
                        .size(22.dp)
                        .clip(CircleShape)
                        .background(InkDark),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("$inCart", color = ChmabaLime, fontSize = 10.sp, fontWeight = FontWeight.ExtraBold)
                }
            }
        }
        Column(modifier = Modifier.padding(horizontal = 11.dp, vertical = 10.dp)) {
            Text(
                product.name,
                color = ChmabaGray900,
                fontSize = 12.5.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                lineHeight = 15.sp,
            )
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    money(product.price),
                    color = ChmabaGray900,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.03).sp,
                    modifier = Modifier.weight(1f),
                )
                Box(
                    modifier = Modifier
                        .size(26.dp)
                        .clip(RoundedCornerShape(9.dp))
                        .background(ChmabaLavender),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(ChmabaIcons.Plus, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(14.dp))
                }
            }
        }
    }
}

/**
 * The bar shown while the cart is empty. It carries the attach-customer action,
 * which otherwise only existed inside the cart sheet.
 */
@Composable
private fun EmptyCartBar(customer: String?, onCustomer: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(PosBg)
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp),
    ) {
        ChmabaButton(
            onClick = onCustomer,
            text = customer ?: "Attach customer",
            modifier = Modifier.fillMaxWidth(),
            variant = if (customer == null) ButtonVariant.Outline else ButtonVariant.Primary,
            size = ButtonSize.Large,
            leadingIcon = {
                Icon(
                    ChmabaIcons.UserPlus,
                    contentDescription = null,
                    tint = if (customer == null) ChmabaBlue else Color.White,
                    modifier = Modifier.size(16.dp),
                )
            },
        )
    }
}

@Composable
private fun CartBar(itemCount: Int, total: Double, onOpenCart: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.985f else 1f, tween(110), label = "cartbar-press")

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(PosBg)
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(58.dp)
                .graphicsLayer { scaleX = scale; scaleY = scale }
                .clip(RoundedCornerShape(16.dp))
                .background(InkDark)
                .clickable(interactionSource = interaction, indication = null, onClick = onOpenCart)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .background(ChmabaLime),
                contentAlignment = Alignment.Center,
            ) {
                Text("$itemCount", color = InkDark, fontSize = 12.sp, fontWeight = FontWeight.ExtraBold)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    if (itemCount == 1) "1 item" else "$itemCount items",
                    color = Color(0xFFA9AAB2),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    money(total),
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.04).sp,
                )
            }
            Text("View cart", color = ChmabaLime, fontSize = 12.5.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.width(6.dp))
            Icon(ChmabaIcons.ChevronRight, contentDescription = null, tint = ChmabaLime, modifier = Modifier.size(16.dp))
        }
    }
}

// ---------------------------------------------------------------- cart sheet

@Composable
private fun CartSheet(
    cart: List<CartLine>,
    customer: String?,
    discountLabel: String?,
    subtotal: Double,
    discount: Double,
    tax: Double,
    total: Double,
    onChangeQuantity: (String, Int) -> Unit,
    onClear: () -> Unit,
    onDiscount: () -> Unit,
    onCustomer: () -> Unit,
    onCharge: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "Current order",
                color = ChmabaGray900,
                fontSize = 16.sp,
                fontWeight = FontWeight.ExtraBold,
                modifier = Modifier.weight(1f),
            )
            if (cart.isNotEmpty()) {
                Text(
                    "Clear",
                    color = ChmabaRed,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .clickable(onClick = onClear)
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }
        }

        Spacer(Modifier.height(14.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ActionChip(
                label = discountLabel ?: "Discount",
                icon = ChmabaIcons.Percent,
                active = discountLabel != null,
                onClick = onDiscount,
                modifier = Modifier.weight(1f),
            )
            ActionChip(
                label = customer ?: "Customer",
                icon = ChmabaIcons.User,
                active = customer != null,
                onClick = onCustomer,
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(14.dp))

        if (cart.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(vertical = 28.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(ChmabaIcons.Cart, contentDescription = null, tint = ChmabaGray300, modifier = Modifier.size(28.dp))
                Spacer(Modifier.height(10.dp))
                Text("Nothing in the cart yet", color = ChmabaGray500, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Text("Tap a product to add it.", color = ChmabaGray400, fontSize = 11.5.sp)
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(SoftPanel),
            ) {
                cart.forEachIndexed { index, line ->
                    if (index > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                    CartLineRow(line, onChangeQuantity)
                }
            }

            Spacer(Modifier.height(16.dp))

            TotalRow("Subtotal", money(subtotal))
            if (discount > 0) {
                Spacer(Modifier.height(8.dp))
                TotalRow("Discount", "-" + money(discount), valueColor = ChmabaRed)
            }
            Spacer(Modifier.height(8.dp))
            TotalRow("Service tax " + rateLabel(com.chmaba.pos.data.orders.Session.serviceTaxRate) + "%", money(tax))
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Total", color = ChmabaGray900, fontSize = 15.sp, fontWeight = FontWeight.ExtraBold)
                Text(
                    money(total),
                    color = ChmabaGray900,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.04).sp,
                )
            }

            Spacer(Modifier.height(16.dp))

            PrimaryAction("Charge ${money(total)}", ChmabaIcons.ArrowRight, onClick = onCharge)
        }
    }
}

@Composable
private fun ActionChip(
    label: String,
    icon: ImageVector,
    active: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .height(44.dp)
            .clip(RoundedCornerShape(13.dp))
            .background(if (active) ChmabaLavender else ChmabaSurface)
            .border(1.dp, if (active) ChmabaBlue else ChmabaGray300, RoundedCornerShape(13.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        Icon(icon, contentDescription = null, tint = if (active) ChmabaBlue else ChmabaGray500, modifier = Modifier.size(15.dp))
        Spacer(Modifier.width(7.dp))
        Text(
            label,
            color = if (active) ChmabaBlue else ChmabaGray700,
            fontSize = 11.5.sp,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun CartLineRow(line: CartLine, onChangeQuantity: (String, Int) -> Unit) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(11.dp))
                    .background(line.product.color),
                contentAlignment = Alignment.Center,
            ) {
                Text(line.product.initials, color = Color(0xFF343039), fontSize = 10.sp, fontWeight = FontWeight.ExtraBold)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    line.product.name,
                    color = ChmabaGray900,
                    fontSize = 12.5.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    if (line.modifiers.isEmpty()) money(line.unitPrice) + " each"
                    else line.modifiers.joinToString(" · ") { it.name } + " · " + money(line.unitPrice),
                    color = ChmabaGray400,
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(8.dp))
            QuantityStepper(
                quantity = line.quantity,
                atMax = line.quantity >= line.product.stock,
                onDecrease = { onChangeQuantity(line.key, line.quantity - 1) },
                onIncrease = { onChangeQuantity(line.key, line.quantity + 1) },
            )
            Spacer(Modifier.width(12.dp))
            Text(
                money(line.lineTotal),
                color = ChmabaGray900,
                fontSize = 12.5.sp,
                fontWeight = FontWeight.ExtraBold,
                modifier = Modifier.width(58.dp),
                textAlign = TextAlign.End,
            )
        }
    }
}

@Composable
private fun QuantityStepper(
    quantity: Int,
    atMax: Boolean,
    onDecrease: () -> Unit,
    onIncrease: () -> Unit,
) {
    Row(
        modifier = Modifier
            .height(34.dp)
            .clip(RoundedCornerShape(11.dp))
            .background(ChmabaSurface)
            .border(1.dp, ChmabaGray300, RoundedCornerShape(11.dp)),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(34.dp).clickable(onClick = onDecrease),
            contentAlignment = Alignment.Center,
        ) {
            Icon(ChmabaIcons.Minus, contentDescription = "Decrease", tint = ChmabaGray700, modifier = Modifier.size(15.dp))
        }
        Text(
            "$quantity",
            color = ChmabaGray900,
            fontSize = 13.sp,
            fontWeight = FontWeight.ExtraBold,
            textAlign = TextAlign.Center,
            modifier = Modifier.width(24.dp),
        )
        Box(
            modifier = Modifier.size(34.dp).clickable(enabled = !atMax, onClick = onIncrease),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                ChmabaIcons.Plus,
                contentDescription = "Increase",
                tint = if (atMax) ChmabaGray300 else ChmabaBlue,
                modifier = Modifier.size(15.dp),
            )
        }
    }
}

@Composable
private fun TotalRow(label: String, value: String, valueColor: Color? = null) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = ChmabaGray500, fontSize = 12.5.sp)
        Text(value, color = valueColor ?: ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun PrimaryAction(
    label: String,
    icon: ImageVector,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(if (enabled) InkDark else ChmabaGray300)
            .clickable(enabled = enabled, onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        Text(label, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.width(8.dp))
        Icon(icon, contentDescription = null, tint = ChmabaLime, modifier = Modifier.size(17.dp))
    }
}

// ---------------------------------------------------------------- modifier sheet

@Composable
private fun ModifierSheet(product: PosProduct, onAdd: (List<SelectedModifier>) -> Unit) {
    val chosen = remember { mutableStateListOf<SelectedModifier>() }

    fun toggle(group: ModifierGroup, option: ModifierOption) {
        val existing = chosen.firstOrNull { chosenOption ->
            group.options.any { it.id == chosenOption.optionId }
        }
        if (existing?.optionId == option.id && !group.required) {
            chosen.remove(existing)
        } else {
            if (existing != null) chosen.remove(existing)
            chosen.add(SelectedModifier(option.id, option.name, option.priceDelta))
        }
    }

    val unitPrice = product.price + chosen.sumOf { it.priceDelta }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(13.dp))
                    .background(product.color),
                contentAlignment = Alignment.Center,
            ) {
                Text(product.initials, color = Color(0xFF343039), fontSize = 12.sp, fontWeight = FontWeight.ExtraBold)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(product.name, color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.height(2.dp))
                Text(
                    if (chosen.isEmpty()) "Choose the options" else chosen.joinToString(" · ") { it.name },
                    color = ChmabaGray400,
                    fontSize = 10.5.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        product.modifierGroups.forEach { group ->
            Spacer(Modifier.height(18.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(group.name, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(6.dp))
                if (group.required) {
                    ChmabaBadge("required", BadgeTone.Neutral)
                }
            }
            Spacer(Modifier.height(8.dp))
            group.options.forEach { option ->
                val selected = chosen.any { it.optionId == option.id }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp)
                        .clip(RoundedCornerShape(13.dp))
                        .background(if (selected) ChmabaLavender else ChmabaSurface)
                        .border(1.dp, if (selected) ChmabaBlue else ChmabaGray300, RoundedCornerShape(13.dp))
                        .clickable { toggle(group, option) }
                        .padding(horizontal = 14.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        option.name,
                        color = if (selected) ChmabaBlue else ChmabaGray900,
                        fontSize = 12.5.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        if (option.priceDelta > 0) "+" + money(option.priceDelta) else "included",
                        color = if (option.priceDelta > 0) ChmabaGray500 else ChmabaGray400,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }

        Spacer(Modifier.height(10.dp))
        PrimaryAction("Add · ${money(unitPrice)}", ChmabaIcons.Check) { onAdd(chosen.toList()) }
    }
}

// ---------------------------------------------------------------- discount sheet

@Composable
private fun DiscountSheet(
    mode: DiscountMode,
    value: String,
    subtotal: Double,
    onApply: (DiscountMode, String) -> Unit,
) {
    var localMode by remember { mutableStateOf(mode) }
    var localValue by remember { mutableStateOf(value) }

    val preview = round2(
        when (localMode) {
            DiscountMode.None -> 0.0
            DiscountMode.Percent -> subtotal * ((localValue.toDoubleOrNull() ?: 0.0) / 100.0)
            DiscountMode.Flat -> localValue.toDoubleOrNull() ?: 0.0
        }.coerceIn(0.0, subtotal),
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Text("Discount", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(4.dp))
        Text("Applied to the whole order.", color = ChmabaGray500, fontSize = 11.5.sp)

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DiscountMode.entries.forEach { entry ->
                val active = entry == localMode
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(44.dp)
                        .clip(RoundedCornerShape(13.dp))
                        .background(if (active) ChmabaBlue else ChmabaSurface)
                        .border(1.dp, if (active) ChmabaBlue else ChmabaGray300, RoundedCornerShape(13.dp))
                        .clickable { localMode = entry },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        entry.label,
                        color = if (active) Color.White else ChmabaGray700,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        if (localMode != DiscountMode.None) {
            Spacer(Modifier.height(14.dp))
            OutlinedTextField(
                value = localValue,
                onValueChange = { localValue = it.filter { ch -> ch.isDigit() || ch == '.' } },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(if (localMode == DiscountMode.Percent) "Percent off" else "Amount off") },
                prefix = { Text(if (localMode == DiscountMode.Percent) "%" else "$", color = ChmabaGray400) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                shape = RoundedCornerShape(13.dp),
                textStyle = TextStyle(fontSize = 17.sp, fontWeight = FontWeight.ExtraBold, color = ChmabaGray900),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ChmabaBlue,
                    unfocusedBorderColor = ChmabaGray300,
                    cursorColor = ChmabaBlue,
                ),
            )
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (localMode == DiscountMode.Percent) {
                    listOf("5", "10", "15", "20").forEach { pct ->
                        QuickChip("$pct%") { localValue = pct }
                    }
                } else {
                    listOf("1", "5", "10").forEach { amount ->
                        QuickChip("$$amount") { localValue = amount }
                    }
                }
            }
            Spacer(Modifier.height(14.dp))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(13.dp))
                    .background(SoftPanel)
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Discount", color = ChmabaGray500, fontSize = 12.5.sp, modifier = Modifier.weight(1f))
                Text("-" + money(preview), color = ChmabaRed, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold)
            }
        }

        Spacer(Modifier.height(18.dp))
        PrimaryAction("Apply discount", ChmabaIcons.Check) { onApply(localMode, localValue) }
    }
}

@Composable
private fun QuickChip(label: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(99.dp))
            .background(ChmabaSurface)
            .border(1.dp, ChmabaGray300, RoundedCornerShape(99.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 13.dp, vertical = 8.dp),
    ) {
        Text(label, color = ChmabaGray700, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
    }
}

// ---------------------------------------------------------------- customer sheet

@Composable
private fun CustomerSheet(
    selected: String?,
    customers: List<Customer>,
    onPick: (String?) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Text("Attach a customer", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(4.dp))
        Text("Attaching a customer earns loyalty points on paid orders.", color = ChmabaGray500, fontSize = 11.5.sp)

        Spacer(Modifier.height(16.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(SoftPanel),
        ) {
            if (customers.isEmpty()) {
                Text(
                    "No customers yet. Add one from More → Customers, then attach them here.",
                    color = ChmabaGray400,
                    fontSize = 11.5.sp,
                    lineHeight = 16.sp,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 16.dp),
                )
            } else {
                customers.forEachIndexed { index, customer ->
                    if (index > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onPick(customer.name) }
                            .padding(horizontal = 14.dp, vertical = 13.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            modifier = Modifier
                                .size(34.dp)
                                .clip(CircleShape)
                                .background(customer.avatarColor),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                customer.initials,
                                color = ChmabaBlue,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.ExtraBold,
                            )
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(customer.name, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(2.dp))
                            Text(customer.contact, color = ChmabaGray400, fontSize = 10.sp)
                        }
                        if (selected == customer.name) {
                            Icon(ChmabaIcons.Check, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Text(
            "Walk-in",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .clickable { onPick(null) }
                .padding(vertical = 12.dp),
        )
    }
}

// ---------------------------------------------------------------- held orders

@Composable
private fun HeldOrdersSheet(
    held: List<HeldOrder>,
    onResume: (HeldOrder) -> Unit,
    onDiscard: (HeldOrder) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Text("Held orders", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(4.dp))
        Text("Parked on this device. Stock is not reserved.", color = ChmabaGray500, fontSize = 11.5.sp)

        Spacer(Modifier.height(16.dp))

        if (held.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(vertical = 26.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(ChmabaIcons.Archive, contentDescription = null, tint = ChmabaGray300, modifier = Modifier.size(26.dp))
                Spacer(Modifier.height(10.dp))
                Text("Nothing held right now", color = ChmabaGray500, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Text("Hold an order to park it here.", color = ChmabaGray400, fontSize = 11.5.sp)
            }
            return@Column
        }

        held.forEach { order ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 10.dp)
                    .clip(RoundedCornerShape(16.dp))
                    .background(SoftPanel)
                    .padding(14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    modifier = Modifier
                        .size(34.dp)
                        .clip(RoundedCornerShape(11.dp))
                        .background(ChmabaLavender),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(ChmabaIcons.Receipt, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(16.dp))
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(order.label, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(2.dp))
                    Text(
                        "${order.itemCount} item(s) · ${money(order.lines.sumOf { it.lineTotal })}",
                        color = ChmabaGray400,
                        fontSize = 10.sp,
                    )
                }
                Text(
                    "Resume",
                    color = ChmabaBlue,
                    fontSize = 11.5.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { onResume(order) }
                        .padding(horizontal = 8.dp, vertical = 5.dp),
                )
                Text(
                    "Discard",
                    color = ChmabaRed,
                    fontSize = 11.5.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { onDiscard(order) }
                        .padding(horizontal = 8.dp, vertical = 5.dp),
                )
            }
        }
    }
}

// ---------------------------------------------------------------- scan sheet

@Composable
private fun ScanSheet(onScanned: (String) -> Unit) {
    var code by remember { mutableStateOf("") }
    val launchScanner = rememberBarcodeScannerLauncher { onScanned(it) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Text("Scan an item", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(4.dp))
        Text(
            "Use the camera scanner, or type the SKU below.",
            color = ChmabaGray500,
            fontSize = 11.5.sp,
            lineHeight = 16.sp,
        )

        Spacer(Modifier.height(16.dp))

        // Scanning opens the device's own scanner screen and comes back here, so
        // the app carries no camera code and no native libraries.
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(132.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(InkDark)
                .clickable(onClick = launchScanner),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(ChmabaIcons.Scan, contentDescription = null, tint = ChmabaLime, modifier = Modifier.size(30.dp))
                Spacer(Modifier.height(10.dp))
                Text(
                    "Open the camera scanner",
                    color = Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(3.dp))
                Text(
                    "Returns here with the scanned code",
                    color = Color(0xFFA9AAB2),
                    fontSize = 10.5.sp,
                )
            }
        }

        Spacer(Modifier.height(14.dp))

        OutlinedTextField(
            value = code,
            onValueChange = { code = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("SKU or barcode") },
            placeholder = { Text("e.g. COF-001", color = ChmabaGray400) },
            singleLine = true,
            shape = RoundedCornerShape(13.dp),
            textStyle = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = ChmabaGray900),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = ChmabaBlue,
                unfocusedBorderColor = ChmabaGray300,
                cursorColor = ChmabaBlue,
            ),
        )

        Spacer(Modifier.height(18.dp))
        PrimaryAction("Add typed code", ChmabaIcons.Check, enabled = code.isNotBlank()) { onScanned(code) }
    }
}

// ---------------------------------------------------------------- payment

@Composable
private fun PaymentSheet(total: Double, onComplete: (Tender) -> Unit, onBack: () -> Unit) {
    var tender by remember { mutableStateOf(Tender.Cash) }
    var cashReceived by remember { mutableStateOf("") }

    val received = cashReceived.toDoubleOrNull() ?: 0.0
    // Money is whole cents; a half-cent of slack guarantees "Exact" satisfies the total.
    val covered = received >= total - 0.005
    val change = round2((received - total).coerceAtLeast(0.0))
    val canComplete = if (tender == Tender.Cash) covered else true

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
    ) {
        Text("Payment", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(12.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaLavender)
                .padding(16.dp),
        ) {
            Text("Amount due", color = ChmabaGray500, fontSize = 10.5.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(
                money(total),
                color = ChmabaGray900,
                fontSize = 30.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.06).sp,
            )
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            TenderTile("Cash", ChmabaIcons.Banknote, tender == Tender.Cash, { tender = Tender.Cash }, Modifier.weight(1f))
            TenderTile("KHQR", ChmabaIcons.Qr, tender == Tender.Khqr, { tender = Tender.Khqr }, Modifier.weight(1f))
        }

        Spacer(Modifier.height(16.dp))

        if (tender == Tender.Cash) {
            Text("Cash received", color = ChmabaGray700, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            OutlinedTextField(
                value = cashReceived,
                onValueChange = { cashReceived = it.filter { ch -> ch.isDigit() || ch == '.' } },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text(money(total), color = ChmabaGray400, fontSize = 14.sp) },
                prefix = { Text("$", color = ChmabaGray400, fontSize = 15.sp) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                shape = RoundedCornerShape(13.dp),
                textStyle = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.ExtraBold, color = ChmabaGray900),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ChmabaBlue,
                    unfocusedBorderColor = ChmabaGray300,
                    focusedContainerColor = ChmabaSurface,
                    unfocusedContainerColor = ChmabaSurface,
                    cursorColor = ChmabaBlue,
                ),
            )
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                QuickChip("Exact") { cashReceived = String.format(Locale.US, "%.2f", total) }
                QuickChip("$20") { cashReceived = "20" }
                QuickChip("$50") { cashReceived = "50" }
                QuickChip("$100") { cashReceived = "100" }
            }
            Spacer(Modifier.height(14.dp))
            if (covered) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(13.dp))
                        .background(GreenSoft)
                        .padding(horizontal = 14.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Change due", color = GreenInk, fontSize = 12.5.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Text(money(change), color = GreenInk, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
                }
            } else {
                Text("Enter at least ${money(total)} to complete the sale.", color = ChmabaGray400, fontSize = 11.sp)
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(Color(0xFFF8FCF5))
                    .border(1.dp, Color(0xFFDFE8D7), RoundedCornerShape(16.dp))
                    .padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Box(
                    modifier = Modifier
                        .size(148.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(ChmabaSurface),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(ChmabaIcons.Qr, contentDescription = null, tint = ChmabaGray900, modifier = Modifier.size(104.dp))
                }
                Spacer(Modifier.height(14.dp))
                Text("KHQR", color = Color(0xFF465142), fontSize = 12.5.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.height(4.dp))
                Text(
                    "Ask the customer to scan to pay ${money(total)}.",
                    color = Color(0xFF84907E),
                    fontSize = 10.5.sp,
                    textAlign = TextAlign.Center,
                    lineHeight = 15.sp,
                )
                Spacer(Modifier.height(10.dp))
                ChmabaBadge("Waiting for payment", BadgeTone.Yellow, showDot = true)
            }
        }

        Spacer(Modifier.height(18.dp))

        PrimaryAction("Complete sale", ChmabaIcons.Check, enabled = canComplete) { onComplete(tender) }

        Spacer(Modifier.height(8.dp))

        Text(
            "Back to cart",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .clickable(onClick = onBack)
                .padding(vertical = 12.dp),
        )
    }
}

@Composable
private fun TenderTile(
    label: String,
    icon: ImageVector,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val border by animateColorAsState(if (selected) ChmabaBlue else ChmabaGray300, tween(160), label = "tender-border")
    val background by animateColorAsState(if (selected) ChmabaLavender else ChmabaSurface, tween(160), label = "tender-bg")
    Column(
        modifier = modifier
            .height(84.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(background)
            .border(1.5.dp, border, RoundedCornerShape(16.dp))
            .clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(icon, contentDescription = null, tint = if (selected) ChmabaBlue else ChmabaGray500, modifier = Modifier.size(22.dp))
        Spacer(Modifier.height(8.dp))
        Text(label, color = if (selected) ChmabaBlue else ChmabaGray700, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
    }
}

// ---------------------------------------------------------------- success

@Composable
private fun SuccessSheet(orderNumber: String, total: String, onDone: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(58.dp)
                .clip(RoundedCornerShape(19.dp))
                .background(GreenSoft),
            contentAlignment = Alignment.Center,
        ) {
            Icon(ChmabaIcons.Check, contentDescription = null, tint = GreenInk, modifier = Modifier.size(26.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text("Sale complete", color = ChmabaGray900, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(6.dp))
        Text(
            // Order numbers come as "#1048", "CHM-000001" or a bare number. Only
            // add a "#" when the value is purely digits, so we never render
            // "##1048" or "#CHM-000001".
            "Order " + if (orderNumber.all { it.isDigit() }) "#$orderNumber" else orderNumber,
            color = ChmabaGray700,
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            "$total received",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "Recorded against " + (com.chmaba.pos.data.orders.Session.storeName ?: "this store") + ". Receipt printing is not wired to a printer yet.",
            color = ChmabaGray400,
            fontSize = 11.sp,
            textAlign = TextAlign.Center,
            lineHeight = 16.sp,
        )
        Spacer(Modifier.height(20.dp))
        PrimaryAction("New sale", ChmabaIcons.Plus, onClick = onDone)
    }
}

@Composable
private fun SendingSheet() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 34.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(10.dp))
        androidx.compose.material3.CircularProgressIndicator(
            color = ChmabaBlue,
            strokeWidth = 3.dp,
            modifier = Modifier.size(34.dp),
        )
        Spacer(Modifier.height(16.dp))
        Text("Sending the sale…", color = ChmabaGray900, fontSize = 15.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(6.dp))
        Text(
            "Keep this screen open until the till confirms.",
            color = ChmabaGray400,
            fontSize = 11.5.sp,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun SaleErrorSheet(message: String, onRetry: () -> Unit, onBackToCart: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(58.dp)
                .clip(RoundedCornerShape(19.dp))
                .background(Color(0xFFFFF0EE)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(ChmabaIcons.Alert, contentDescription = null, tint = ChmabaRed, modifier = Modifier.size(26.dp))
        }
        Spacer(Modifier.height(16.dp))
        Text("The sale was not recorded", color = ChmabaGray900, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(6.dp))
        Text(
            message,
            color = ChmabaGray500,
            fontSize = 12.sp,
            textAlign = TextAlign.Center,
            lineHeight = 17.sp,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "The cart is untouched — nothing was charged.",
            color = ChmabaGray400,
            fontSize = 11.sp,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(20.dp))
        PrimaryAction("Try again", ChmabaIcons.Refresh, onClick = onRetry)
        Spacer(Modifier.height(8.dp))
        Text(
            "Back to cart",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .clickable(onClick = onBackToCart)
                .padding(vertical = 12.dp),
        )
    }
}
