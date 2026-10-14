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
import com.chmaba.pos.ui.screens.products.sampleProduct
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

    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
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

                    NavTab.Pos -> POSScreen()

                    NavTab.Orders -> if (openOrder == null) {
                        OrdersScreen(
                            storeName = Session.storeName ?: "Main Counter",
                            state = ordersViewModel.state,
                            onOpenOrder = { openOrder = it },
                            onRetry = { ordersViewModel.load() },
                        )
                    } else {
                        OrderDetailScreen(
                            onBack = { openOrder = null },
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
                                    onRetry = { customersViewModel.load() },
                                )
                            } else {
                                CustomerDetailScreen(onBack = { openCustomer = null })
                            }

                            dest == MoreDest.Categories -> CategoriesScreen(
                                onRenameCategory = { },
                            )

                            dest == MoreDest.Inventory -> InventoryScreen()

                            dest == MoreDest.Products -> if (editingProduct == null) {
                                ProductsScreen(
                                    onOpenProduct = { editingProduct = it },
                                    onAddProduct = { editingProduct = "new" },
                                )
                            } else {
                                ProductEditorScreen(
                                    product = sampleProduct(editingProduct),
                                    onBack = { editingProduct = null },
                                    onSave = { _, _, _ -> editingProduct = null },
                                )
                            }

                            dest == MoreDest.Reports -> ReportsScreen(
                                state = reportsViewModel.state,
                                period = reportsViewModel.period,
                                onSelectPeriod = reportsViewModel::select,
                                onRetry = reportsViewModel::reload,
                            )

                            dest == MoreDest.Purchasing -> PurchasingScreen()

                            dest == MoreDest.Suppliers -> SuppliersScreen()

                            dest == MoreDest.Settings -> SettingsScreen(
                                storeName = Session.storeName ?: "Your store",
                                onSignOut = onSignOut,
                            )

                            dest == MoreDest.Billing -> PlansScreen(onBack = { moreDest = null })

                            else -> PlaceholderScreen(
                                title = dest.name,
                                subtitle = "Reachable from More.",
                                icon = ChmabaIcons.Package,
                            )
                        }
                    }
                }
            }
        }

        NavDivider()
        ChmabaBottomNav(
            items = NAV_ITEMS,
            selected = tab,
            onSelect = { tab = it },
        )
    }
    }
}

/** Nothing here is built yet; shown until each screen is ported. */
@Composable
private fun PlaceholderScreen(
    title: String,
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
            MoreRow("Team", "Members, roles, invites", ChmabaIcons.UserPlus, MoreDest.Team),
            MoreRow("Activity", "Everything your team changed", ChmabaIcons.Clock, MoreDest.Activity),
        ),
        "Account" to listOf(
            MoreRow("Billing & plans", "Live plan pricing", ChmabaIcons.CreditCard, MoreDest.Billing),
            MoreRow("Settings", "Store, tax, receipts, hardware", ChmabaIcons.Sliders, MoreDest.Settings),
            MoreRow("Help & support", "Guides and the AI assistant", ChmabaIcons.Message, MoreDest.Help),
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
        Text("Main Counter · Cedar & Stone", color = ChmabaGray500, fontSize = 12.5.sp)

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
