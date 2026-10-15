package com.chmaba.pos.ui.screens.shell

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.Text
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import kotlinx.coroutines.launch
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.ui.components.BottomNavItem
import com.chmaba.pos.ui.components.ChmabaBottomNav
import com.chmaba.pos.ui.components.ChmabaLogo
import com.chmaba.pos.ui.components.NavDivider
import com.chmaba.pos.ui.components.NavTab
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.screens.categories.CategoriesScreen
import com.chmaba.pos.ui.screens.customers.CustomerDetailScreen
import com.chmaba.pos.ui.screens.customers.CustomersScreen
import com.chmaba.pos.ui.screens.dashboard.DashboardScreen
import com.chmaba.pos.ui.screens.inventory.InventoryScreen
import com.chmaba.pos.ui.screens.orders.OrderDetailScreen
import com.chmaba.pos.ui.screens.orders.OrdersScreen
import com.chmaba.pos.ui.screens.plans.PlansScreen
import com.chmaba.pos.ui.screens.pos.POSScreen
import com.chmaba.pos.ui.screens.products.ProductEditorScreen
import com.chmaba.pos.ui.screens.products.ProductsScreen
import com.chmaba.pos.ui.screens.purchasing.PurchasingScreen
import com.chmaba.pos.ui.screens.reports.ReportsScreen
import com.chmaba.pos.ui.screens.settings.SettingsScreen
import com.chmaba.pos.ui.screens.suppliers.SuppliersScreen
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaSurface

private val ShellBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)

/** Destinations reachable from the More tab (the web sidebar's other pages). */
enum class MoreDest { Products, Categories, Customers, Inventory, Purchasing, Suppliers, Reports, Team, Activity, Billing, Settings, Help }

private val NAV_ITEMS = listOf(
    BottomNavItem(NavTab.Home, ChmabaIcons.Home, "Home"),
    BottomNavItem(NavTab.Pos, ChmabaIcons.Cart, "POS"),
    BottomNavItem(NavTab.Orders, ChmabaIcons.Receipt, "Orders"),
    BottomNavItem(NavTab.More, ChmabaIcons.Sliders, "More"),
)

/**
 * Post-login shell: content on top, persistent bottom navigation underneath.
 *
 * This replaces the web's left sidebar. The active tab is driven by [NavTab] so
 * every screen can deep-link to a tab (e.g. Dashboard "New sale" -> POS).
 */
@Composable
fun MainShell(
    modifier: Modifier = Modifier,
    onSignOut: () -> Unit = {},
) {
    var tab by remember { mutableStateOf(NavTab.Home) }
    var openOrder by remember { mutableStateOf<String?>(null) }
    var moreDest by remember { mutableStateOf<MoreDest?>(null) }
    var openCustomer by remember { mutableStateOf<String?>(null) }
    var editingProduct by remember { mutableStateOf<String?>(null) }

    // Actions the web POS offers that this app does not implement. Without a
    // notice they were simply dead buttons: tapping one did nothing at all.
    var notice by remember { mutableStateOf<String?>(null) }
    val notYet: (String) -> Unit = { what ->
        notice = "$what isn't in the Android app yet. Use the web POS for it."
    }

    // Loads orders from the API; shared with the Orders tab.
    val ordersViewModel: com.chmaba.pos.ui.screens.orders.OrdersViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    // Loads customers from the API.
    val customersViewModel: com.chmaba.pos.ui.screens.customers.CustomersViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    // Loads GET /reports/summary. Shared by the Overview and the Reports screen
    // so both read the same window rather than disagreeing about "today".
    val reportsViewModel: com.chmaba.pos.data.reports.ReportsViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    // Loads GET /orders/{id} for the order detail screen.
    val orderDetailViewModel: com.chmaba.pos.ui.screens.orders.OrderDetailViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    // Loads GET /customers/{id} for the customer detail screen.
    val customerDetailViewModel: com.chmaba.pos.ui.screens.customers.CustomerDetailViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    // Loads the catalogue. Held here so the product editor can look a product up
    // in the real list; ProductsScreen receives this same instance.
    val productsViewModel: com.chmaba.pos.ui.screens.store.ProductsViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    // Categories, so the product editor can turn a category name into the id the
    // API expects. Shared with CategoriesScreen.
    val categoriesViewModel: com.chmaba.pos.ui.screens.store.CategoriesViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel()

    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val context = androidx.compose.ui.platform.LocalContext.current
    val openDrawer: () -> Unit = { scope.launch { drawerState.open() } }
    val closeDrawer: () -> Unit = { scope.launch { drawerState.close() } }

    // Nested destinations unwind one level at a time, deepest first.
    BackHandler(enabled = openOrder != null || openCustomer != null || editingProduct != null || moreDest != null) {
        when {
            editingProduct != null -> editingProduct = null
            openCustomer != null -> openCustomer = null
            moreDest != null -> moreDest = null
            else -> openOrder = null
        }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(
                modifier = Modifier.width(304.dp),
                drawerContainerColor = ChmabaSurface,
            ) {
                DrawerContent(
                    selectedTab = tab,
                    selectedDest = moreDest,
                    onSignOut = {
                        closeDrawer()
                        onSignOut()
                    },
                    onSelectTab = { next ->
                        tab = next
                        moreDest = null
                        openOrder = null
                        openCustomer = null
                        editingProduct = null
                        closeDrawer()
                    },
                    onSelectDest = { dest ->
                        moreDest = dest
                        tab = NavTab.More
                        openOrder = null
                        openCustomer = null
                        editingProduct = null
                        closeDrawer()
                    },
                )
            }
        },
    ) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(ShellBg),
    ) {
        Box(Modifier.weight(1f)) {
            Crossfade(
                targetState = tab,
                animationSpec = tween(durationMillis = 220),
                label = "shell-tab",
            ) { current ->
                when (current) {
                    NavTab.Home -> DashboardScreen(
                        greetingName = Session.userName ?: "there",
                        storeName = Session.storeName ?: "your store",
                        state = reportsViewModel.state,
                        period = reportsViewModel.period,
                        onSelectPeriod = reportsViewModel::select,
                        onRetry = reportsViewModel::reload,
                        onNewSale = { tab = NavTab.Pos },
                        onOpenOrders = { tab = NavTab.Orders },
                        onOpenProducts = { moreDest = MoreDest.Products; tab = NavTab.More },
                        onOpenInventory = { moreDest = MoreDest.Inventory; tab = NavTab.More },
                        onOpenTeam = { moreDest = MoreDest.Team; tab = NavTab.More },
                        onOpenReports = { moreDest = MoreDest.Reports; tab = NavTab.More },
                        onOpenMenu = openDrawer,
                    )

                    NavTab.Pos -> POSScreen(
                        // The attach-customer sheet lists real customers.
                        customers = (customersViewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)
                            ?.data
                            .orEmpty(),
                    )

                    NavTab.Orders -> if (openOrder == null) {
                        OrdersScreen(
                            storeName = Session.storeName ?: "Your store",
                            state = ordersViewModel.state,
                            onOpenOrder = { openOrder = it },
                            onRetry = { ordersViewModel.load() },
                        )
                    } else {
                        // The tapped row only holds a summary, so fetch the full
                        // order whenever a different one is opened.
                        LaunchedEffect(openOrder) {
                            openOrder?.let { orderDetailViewModel.load(it) }
                        }
                        OrderDetailScreen(
                            state = orderDetailViewModel.state,
                            onBack = { openOrder = null },
                            onRetry = orderDetailViewModel::retry,
                            onPrintReceipt = { notYet("Printing a receipt") },
                            onRefundOrder = { onDone -> orderDetailViewModel.refund(onDone) },
                            planAllowsRefunds = Session.hasFeature("refunds"),
                            refunding = orderDetailViewModel.refunding,
                            refundError = orderDetailViewModel.refundError,
                            onDismissRefundError = orderDetailViewModel::clearRefundError,
                            onCancelOrder = { onDone -> orderDetailViewModel.cancel(onDone) },
                            cancelling = orderDetailViewModel.cancelling,
                            cancelError = orderDetailViewModel.cancelError,
                            onDismissCancelError = orderDetailViewModel::clearCancelError,
                        )
                    }

                    NavTab.More -> {
                        val dest = moreDest
                        when {
                            dest == null -> MoreScreen(onOpen = { moreDest = it })

                            dest == MoreDest.Customers -> if (openCustomer == null) {
                                CustomersScreen(
                                    state = customersViewModel.state,
                                    onOpenCustomer = { openCustomer = it },
                                    onCreateCustomer = { name, phone, email, onCreated ->
                                        customersViewModel.create(name, phone, email, onCreated)
                                    },
                                    creating = customersViewModel.creating,
                                    createError = customersViewModel.createError,
                                    onDismissCreateError = customersViewModel::clearCreateError,
                                    onRetry = { customersViewModel.load() },
                                )
                            } else {
                                // The tapped row only holds a summary, so fetch the
                                // full customer whenever a different one is opened.
                                LaunchedEffect(openCustomer) {
                                    openCustomer?.let { customerDetailViewModel.load(it) }
                                }
                                CustomerDetailScreen(
                                    state = customerDetailViewModel.state,
                                    onBack = { openCustomer = null },
                                    onRetry = customerDetailViewModel::retry,
                                    onUpdateCustomer = { name, phone, email, onUpdated ->
                                        customerDetailViewModel.update(name, phone, email, onUpdated)
                                    },
                                    updating = customerDetailViewModel.updating,
                                    updateError = customerDetailViewModel.updateError,
                                    onDismissUpdateError = customerDetailViewModel::clearUpdateError,
                                    onOpenOrder = { notYet("Opening an order from here") },
                                )
                            }

                            dest == MoreDest.Categories -> CategoriesScreen()

                            dest == MoreDest.Inventory -> InventoryScreen()

                            dest == MoreDest.Products -> {
                                val target = editingProduct
                                // The editor works in category names; the API takes
                                // ids, so hand it the categories the store has.
                                val categoryOptions =
                                    (categoriesViewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)
                                        ?.data
                                        ?.map { com.chmaba.pos.ui.screens.products.CategoryOption(it.id, it.name) }
                                        ?.filter { it.id.isNotBlank() }
                                        .orEmpty()
                                when {
                                    target == null -> ProductsScreen(
                                        viewModel = productsViewModel,
                                        onOpenProduct = { editingProduct = it },
                                        onAddProduct = { editingProduct = "new" },
                                    )

                                    target == "new" -> ProductEditorScreen(
                                        product = null,
                                        saving = productsViewModel.saving,
                                        error = productsViewModel.saveError,
                                        categoryOptions = categoryOptions,
                                        onBack = { editingProduct = null },
                                        onSave = { body ->
                                            productsViewModel.save(null, body) { editingProduct = null }
                                        },
                                    )

                                    else -> {
                                        // The editor seeds its fields from its first
                                        // composition, so it is only built once the
                                        // real product is in hand.
                                        val catalogue = productsViewModel.state
                                        val editing = if (catalogue is com.chmaba.pos.data.store.LoadState.Ready) {
                                            catalogue.data.firstOrNull { it.id == target }
                                        } else {
                                            null
                                        }
                                        if (editing != null) {
                                            val id = editing.id
                                            ProductEditorScreen(
                                                product = editing,
                                                saving = productsViewModel.saving,
                                                error = productsViewModel.saveError,
                                                categoryOptions = categoryOptions,
                                                savingVariants = productsViewModel.savingVariants,
                                                variantsError = productsViewModel.variantsError,
                                                variantsSaved = productsViewModel.variantsSaved,
                                                onVariantsSavedShown = productsViewModel::clearVariantsSaved,
                                                onSaveVariants = { rows ->
                                                    productsViewModel.saveVariants(id, rows) { }
                                                },
                                                onBack = { editingProduct = null },
                                                onSave = { body ->
                                                    productsViewModel.save(id, body) { editingProduct = null }
                                                },
                                            )
                                        } else {
                                            PlaceholderScreen(
                                                title = "Product",
                                                subtitle = when (catalogue) {
                                                    is com.chmaba.pos.data.store.LoadState.Failed -> catalogue.message
                                                    is com.chmaba.pos.data.store.LoadState.Ready -> "That product is not in this catalogue."
                                                    else -> "Loading the catalogue…"
                                                },
                                                icon = ChmabaIcons.Package,
                                            )
                                        }
                                    }
                                }
                            }

                            dest == MoreDest.Reports -> ReportsScreen(
                                state = reportsViewModel.state,
                                period = reportsViewModel.period,
                                onSelectPeriod = reportsViewModel::select,
                                onRetry = reportsViewModel::reload,
                                onExport = {
                                    scope.launch {
                                        reportsViewModel.export { csv ->
                                            com.chmaba.pos.ui.components.shareCsv(
                                                context,
                                                "gdt-invoices.csv",
                                                csv,
                                                "Export invoices",
                                            )
                                        }
                                    }
                                },
                                exporting = reportsViewModel.exporting,
                                exportError = reportsViewModel.exportError,
                                // The API plan-gates this endpoint on advanced_reports, so the
                                // control says so before the reader hits it.
                                planAllowsExport = Session.hasFeature("advanced_reports"),
                            )

                            // Real: the entries come from GET /audit-logs.
                            dest == MoreDest.Activity -> com.chmaba.pos.ui.screens.activity.ActivityScreen()

                            dest == MoreDest.Purchasing -> PurchasingScreen(
                                onOpenOrder = { notYet("Opening a purchase order") },
                                onNewOrder = { notYet("Creating a purchase order") },
                                onCreateOrdersForSuggestions = { notYet("Creating orders from suggestions") },
                                planAllowsPurchasing = Session.hasFeature("purchasing"),
                            )

                            dest == MoreDest.Suppliers -> SuppliersScreen(
                                onOpenSupplier = { notYet("Opening a supplier") },
                                // Plan-driven, so the button reflects the workspace that
                                // is actually signed in rather than a hardcoded feature.
                                planAllowsPurchasing = Session.hasFeature("purchasing"),
                            )

                            // Real: the guides come from GET /support/articles.
                            dest == MoreDest.Help -> com.chmaba.pos.ui.screens.help.HelpScreen()

                            dest == MoreDest.Settings -> SettingsScreen(
                                storeName = Session.storeName ?: "Your store",
                                planFeatures = Session.planFeatures.toList(),
                                onOpenSection = { notYet("That settings section") },
                                onSignOut = onSignOut,
                            )

                            dest == MoreDest.Billing -> PlansScreen(onBack = { moreDest = null })

                            // Real: the members come from GET /team.
                            dest == MoreDest.Team -> com.chmaba.pos.ui.screens.team.TeamScreen()

                            else -> PlaceholderScreen(
                                title = dest.name,
                                // The reader is already in More, so pointing them
                                // "from More" made no sense. Say what is true.
                                subtitle = "Not built in the Android app yet. Use the web POS for " +
                                    "this screen.",
                                icon = ChmabaIcons.Package,
                            )
                        }
                    }
                }
            }
        }

        notice?.let { message ->
            ShellNotice(message) { notice = null }
        }

        NavDivider()
        ChmabaBottomNav(
            items = NAV_ITEMS,
            selected = tab,
            onSelect = { next ->
                tab = next
                // Coming back to More shows the list, not whatever screen was open: a tab
                // is a destination, and the drawer already behaves this way.
                if (next == NavTab.More) moreDest = null
            },
        )
    }
    }
}

/**
 * A dismissible one-line notice shown above the bottom bar. It is how an action
 * that is not built yet says so, rather than doing nothing when tapped.
 */
@Composable
private fun ShellNotice(message: String, onDismiss: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFFFFF6DF))
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            message,
            color = ChmabaGray900,
            fontSize = 11.5.sp,
            lineHeight = 16.sp,
            modifier = Modifier.weight(1f),
        )
        Text(
            "Dismiss",
            color = ChmabaBlue,
            fontSize = 11.5.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .padding(start = 12.dp)
                .clickable(onClick = onDismiss),
        )
    }
}

/** Nothing here is built yet; shown until each screen is ported. */
@Composable
private fun PlaceholderScreen(    title: String,
    subtitle: String,
    icon: ImageVector,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ShellBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            title,
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(2.dp))
        Text(subtitle, color = ChmabaGray500, fontSize = 12.5.sp)
        Spacer(Modifier.height(20.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                modifier = Modifier
                    .size(46.dp)
                    .clip(RoundedCornerShape(15.dp))
                    .background(ChmabaLavender),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(22.dp))
            }
            Spacer(Modifier.height(14.dp))
            Text(
                "Being ported",
                color = ChmabaGray900,
                fontSize = 14.sp,
                fontWeight = FontWeight.ExtraBold,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                "This screen is designed and approved in the prototype; the Android build lands next.",
                color = ChmabaGray400,
                fontSize = 11.5.sp,
                lineHeight = 17.sp,
            )
        }
    }
}

private data class MoreRow(
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val dest: MoreDest,
)

/** The "More" tab — the web sidebar's remaining destinations. */
@Composable
private fun MoreScreen(onOpen: (MoreDest) -> Unit) {
    val groups = listOf(
        "Selling" to listOf(
            MoreRow("Products", "Catalog, variants, serials", ChmabaIcons.Package, MoreDest.Products),
            MoreRow("Categories", "Organise the catalog", ChmabaIcons.Tag, MoreDest.Categories),
            MoreRow("Customers", "Profiles, orders, loyalty", ChmabaIcons.Users, MoreDest.Customers),
        ),
        "Stock" to listOf(
            MoreRow("Inventory", "Levels, adjust, receive", ChmabaIcons.Boxes, MoreDest.Inventory),
            MoreRow("Purchasing", "Purchase orders", ChmabaIcons.Truck, MoreDest.Purchasing),
            MoreRow("Suppliers", "Who you buy from", ChmabaIcons.Store, MoreDest.Suppliers),
        ),
        "Business" to listOf(
            MoreRow("Reports", "Sales, margin, breakdowns", ChmabaIcons.BarChart, MoreDest.Reports),
            MoreRow("Team", "Members and their roles", ChmabaIcons.UserPlus, MoreDest.Team),
            MoreRow("Activity", "Everything your team changed", ChmabaIcons.Clock, MoreDest.Activity),
        ),
        "Account" to listOf(
            MoreRow("Billing & plans", "Live plan pricing", ChmabaIcons.CreditCard, MoreDest.Billing),
            MoreRow("Settings", "Store, tax, payments", ChmabaIcons.Sliders, MoreDest.Settings),
            MoreRow("Help & support", "Guides for your store", ChmabaIcons.Message, MoreDest.Help),
        ),
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ShellBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            "More",
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            // The store, then the company when the workspace names one. Both come from the same
            // workspace read, so neither is guessed at.
            listOfNotNull(Session.storeName ?: "Your store", Session.companyName).joinToString(" · "),
            color = ChmabaGray500,
            fontSize = 12.5.sp,
        )

        groups.forEach { (heading, rows) ->
            Spacer(Modifier.height(18.dp))
            Text(
                heading.uppercase(),
                color = ChmabaGray400,
                fontSize = 9.5.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = 1.1.sp,
            )
            Spacer(Modifier.height(8.dp))
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(ChmabaSurface),
            ) {
                rows.forEachIndexed { index, row ->
                    if (index > 0) {
                        Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                    }
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onOpen(row.dest) }
                            .padding(horizontal = 16.dp, vertical = 13.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Box(
                            modifier = Modifier
                                .size(34.dp)
                                .clip(RoundedCornerShape(11.dp))
                                .background(ChmabaLavender),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(row.icon, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(17.dp))
                        }
                        Column(Modifier.weight(1f)) {
                            Text(row.title, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(2.dp))
                            Text(row.subtitle, color = ChmabaGray400, fontSize = 10.sp)
                        }
                        Icon(
                            ChmabaIcons.ChevronRight,
                            contentDescription = null,
                            tint = ChmabaGray400,
                            modifier = Modifier.size(16.dp),
                        )
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

private data class DrawerEntry(
    val label: String,
    val icon: ImageVector,
    val tab: NavTab? = null,
    val dest: MoreDest? = null,
)

/**
 * The left navigation drawer — every destination in one place, so a cashier can
 * jump straight to a screen instead of going through More.
 */
@Composable
private fun DrawerContent(
    selectedTab: NavTab,
    selectedDest: MoreDest?,
    onSelectTab: (NavTab) -> Unit,
    onSelectDest: (MoreDest) -> Unit,
    onSignOut: () -> Unit,
) {
    val groups = listOf(
        null to listOf(
            DrawerEntry("Home", ChmabaIcons.Home, tab = NavTab.Home),
            DrawerEntry("POS", ChmabaIcons.Cart, tab = NavTab.Pos),
            DrawerEntry("Orders", ChmabaIcons.Receipt, tab = NavTab.Orders),
        ),
        "Selling" to listOf(
            DrawerEntry("Products", ChmabaIcons.Package, dest = MoreDest.Products),
            DrawerEntry("Customers", ChmabaIcons.Users, dest = MoreDest.Customers),
            DrawerEntry("Categories", ChmabaIcons.Tag, dest = MoreDest.Categories),
        ),
        "Stock" to listOf(
            DrawerEntry("Inventory", ChmabaIcons.Boxes, dest = MoreDest.Inventory),
            DrawerEntry("Purchasing", ChmabaIcons.Truck, dest = MoreDest.Purchasing),
            DrawerEntry("Suppliers", ChmabaIcons.Store, dest = MoreDest.Suppliers),
        ),
        "Business" to listOf(
            DrawerEntry("Reports", ChmabaIcons.BarChart, dest = MoreDest.Reports),
            DrawerEntry("Team", ChmabaIcons.UserPlus, dest = MoreDest.Team),
            DrawerEntry("Activity", ChmabaIcons.Clock, dest = MoreDest.Activity),
        ),
        "Account" to listOf(
            DrawerEntry("Billing & plans", ChmabaIcons.CreditCard, dest = MoreDest.Billing),
            DrawerEntry("Settings", ChmabaIcons.Sliders, dest = MoreDest.Settings),
            DrawerEntry("Help & support", ChmabaIcons.Message, dest = MoreDest.Help),
        ),
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ChmabaSurface)
            .padding(horizontal = 12.dp, vertical = 20.dp),
    ) {
        ChmabaLogo(modifier = Modifier.padding(horizontal = 8.dp))
        Spacer(Modifier.height(6.dp))
        Text(
            listOfNotNull(Session.storeName, Session.userName).joinToString(" · ").ifBlank { "Chmaba" },
            color = ChmabaGray400,
            fontSize = 10.5.sp,
            modifier = Modifier.padding(horizontal = 8.dp),
        )
        Spacer(Modifier.height(18.dp))

        // Only the list scrolls. Sign out is pinned below it so it is always
        // reachable — it previously sat under the fold, which made the app look
        // like it could not be signed out of.
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
        groups.forEach { (heading, entries) ->
            if (heading != null) {
                Text(
                    heading.uppercase(),
                    color = ChmabaGray400,
                    fontSize = 9.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 1.1.sp,
                    modifier = Modifier.padding(start = 8.dp, top = 8.dp, bottom = 6.dp),
                )
            }
            entries.forEach { entry ->
                val selected = if (entry.tab != null) {
                    selectedDest == null && selectedTab == entry.tab
                } else {
                    selectedDest == entry.dest
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(11.dp))
                        .background(if (selected) ChmabaLavender else Color.Transparent)
                        .clickable {
                            if (entry.tab != null) onSelectTab(entry.tab) else entry.dest?.let(onSelectDest)
                        }
                        .padding(horizontal = 10.dp, vertical = 11.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        entry.icon,
                        contentDescription = null,
                        tint = if (selected) ChmabaBlue else ChmabaGray400,
                        modifier = Modifier.size(18.dp),
                    )
                    Spacer(Modifier.width(12.dp))
                    Text(
                        entry.label,
                        color = if (selected) ChmabaBlue else ChmabaGray900,
                        fontSize = 12.5.sp,
                        fontWeight = if (selected) FontWeight.ExtraBold else FontWeight.Bold,
                    )
                }
                Spacer(Modifier.height(2.dp))
            }
            Spacer(Modifier.height(4.dp))
        }
        }

        Spacer(Modifier.height(10.dp))
        Box(Modifier.fillMaxWidth().height(1.dp).background(Color(0xFFF2F2F5)))
        Spacer(Modifier.height(6.dp))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(11.dp))
                .clickable(onClick = onSignOut)
                .padding(horizontal = 10.dp, vertical = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                ChmabaIcons.Lock,
                contentDescription = null,
                tint = Color(0xFFC2564B),
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(12.dp))
            Text(
                "Sign out",
                color = Color(0xFFC2564B),
                fontSize = 12.5.sp,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}
