package com.chmaba.pos.ui.screens.customers

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.material3.AlertDialog
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface

private val CustomersBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)

/**
 * A customer. CustomerRead carries name, phone, email, points and created_at;
 * the order count and lifetime spend exist only on the detail payload, so they
 * stay zero/dash until the detail is loaded.
 */
data class Customer(
    val name: String,
    val contact: String,
    val orders: Int,
    val spent: String,
    val points: Int,
    val avatarColor: Color,
    val initials: String,
    /** UUID; the detail screen loads `GET /customers/{id}` with it. */
    val id: String = "",
    /** CustomerRead.created_at, rendered as "Customer since". */
    val since: String? = null,
)

data class CustomerOrder(
    val number: String,
    val detail: String,
    val total: String,
)

/** One customer from `GET /customers/{id}`, with their real order history. */
data class CustomerDetail(
    val customer: Customer,
    val orders: List<CustomerOrder>,
)

@Composable
fun CustomersScreen(
    modifier: Modifier = Modifier,
    state: LoadState<List<Customer>> = LoadState.Loading,
    onOpenCustomer: (String) -> Unit = {},
    onCreateCustomer: (String, String?, String?, () -> Unit) -> Unit = { _, _, _, _ -> },
    creating: Boolean = false,
    createError: String? = null,
    onDismissCreateError: () -> Unit = {},
    onRetry: () -> Unit = {},
) {
    val customers = (state as? LoadState.Ready)?.data.orEmpty()
    // Whether the add form is open; the form owns its own field values.
    var adding by remember { mutableStateOf(false) }

    if (adding) {
        AddCustomerDialog(
            creating = creating,
            error = createError,
            onDismiss = {
                onDismissCreateError()
                adding = false
            },
            // The view model runs onCreated only on success, which closes the form.
            onCreate = { name, phone, email ->
                onCreateCustomer(name, phone, email) { adding = false }
            },
        )
    }
    var query by remember { mutableStateOf("") }
    val visible = if (query.isBlank()) customers else customers.filter {
        it.name.contains(query, ignoreCase = true) || it.contact.contains(query, ignoreCase = true)
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(CustomersBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Customers",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text("Shared across your stores.", color = ChmabaGray500, fontSize = 12.5.sp)
            }
            ChmabaButton(
                onClick = { adding = true },
                text = "Add",
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
                leadingIcon = { Icon(ChmabaIcons.Plus, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp)) },
            )
        }

        Spacer(Modifier.height(16.dp))

        ChmabaTextField(
            value = query,
            onValueChange = { query = it },
            label = "Search",
            placeholder = "Search by name or phone…",
        )

        Spacer(Modifier.height(4.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            visible.forEachIndexed { index, customer ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpenCustomer(customer.id) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Avatar(customer)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            customer.name,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(customer.contact, color = ChmabaGray400, fontSize = 10.sp)
                    }
                    Text(
                        "${customer.points} pts",
                        color = ChmabaGray900,
                        fontSize = 12.5.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                }
            }
            if (state is LoadState.Loading) {
                Text(
                    "Loading customers…",
                    color = ChmabaGray400,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(20.dp),
                )
            } else if (state is LoadState.Failed) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        "Could not load customers",
                        color = ChmabaGray900,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        (state as LoadState.Failed).message,
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
            } else if (visible.isEmpty()) {
                Text(
                    "No customers match that search.",
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
private fun Avatar(customer: Customer) {
    Box(
        modifier = Modifier
            .size(36.dp)
            .clip(CircleShape)
            .background(customer.avatarColor),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            customer.initials,
            color = Color(0xFF44424A),
            fontSize = 11.sp,
            fontWeight = FontWeight.ExtraBold,
        )
    }
}

/**
 * One customer from `GET /customers/{id}`: real contact details, order count,
 * lifetime spend and order history. The list row only carries a summary, so the
 * detail is fetched when the row is opened rather than rebuilt from it.
 */
/**
 * The add-customer form. Only a name is required, matching CustomerCreateRequest;
 * loyalty points are earned on paid orders and are not set here.
 */
@Composable
private fun AddCustomerDialog(
    creating: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onCreate: (String, String?, String?) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = ChmabaSurface,
        title = {
            Text("Add customer", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        },
        text = {
            Column {
                ChmabaTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = "Name",
                    placeholder = "e.g. Sokha Lim",
                )
                Spacer(Modifier.height(10.dp))
                ChmabaTextField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = "Phone",
                    placeholder = "Optional",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                )
                Spacer(Modifier.height(10.dp))
                ChmabaTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = "Email",
                    placeholder = "Optional",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                )
                if (error != null) {
                    Spacer(Modifier.height(10.dp))
                    Text(error, color = ChmabaRed, fontSize = 11.sp, lineHeight = 15.sp)
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    "Points are earned on paid orders, so they are not set here.",
                    color = ChmabaGray400,
                    fontSize = 10.sp,
                    lineHeight = 14.sp,
                )
            }
        },
        confirmButton = {
            ChmabaButton(
                onClick = { onCreate(name, phone, email) },
                text = if (creating) "Saving…" else "Add",
                enabled = name.isNotBlank() && !creating,
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
fun CustomerDetailScreen(
    modifier: Modifier = Modifier,
    state: LoadState<CustomerDetail> = LoadState.Loading,
    onBack: () -> Unit = {},
    onRetry: () -> Unit = {},
    onEdit: () -> Unit = {},
    onOpenOrder: (String) -> Unit = {},
) {
    val loaded = (state as? LoadState.Ready)?.data

    if (loaded == null) {
        // Loading or failed keeps the back affordance and says what is
        // happening, rather than presenting an empty customer.
        Column(
            modifier = modifier
                .fillMaxSize()
                .background(CustomersBg)
                .padding(16.dp),
        ) {
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
            Spacer(Modifier.height(16.dp))
            if (state is LoadState.Failed) {
                Text("Could not load this customer", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.height(6.dp))
                Text(state.message, color = ChmabaGray500, fontSize = 11.5.sp, lineHeight = 17.sp)
                Spacer(Modifier.height(12.dp))
                ChmabaButton(
                    onClick = onRetry,
                    text = "Try again",
                    variant = ButtonVariant.Outline,
                    size = ButtonSize.Small,
                )
            } else {
                Text("Loading customer…", color = ChmabaGray400, fontSize = 12.sp)
            }
        }
        return
    }

    val customer = loaded.customer
    val history = loaded.orders

    var adjustPoints by remember { mutableIntStateOf(10) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(CustomersBg)
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
                    customer.name,
                    color = ChmabaGray900,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    customer.since?.let { "Customer since $it" } ?: customer.contact,
                    color = ChmabaGray500,
                    fontSize = 11.sp,
                )
            }
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(ChmabaSurface)
                    .clickable(onClick = onEdit),
                contentAlignment = Alignment.Center,
            ) {
                Icon(ChmabaIcons.Pencil, contentDescription = "Edit", tint = ChmabaGray500, modifier = Modifier.size(16.dp))
            }
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Stat("Orders", customer.orders.toString(), Modifier.weight(1f))
            Stat("Spent", customer.spent, Modifier.weight(1f))
            Stat("Points", customer.points.toString(), Modifier.weight(1f))
        }

        Spacer(Modifier.height(12.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface)
                .padding(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Loyalty points", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
                    Spacer(Modifier.height(2.dp))
                    Text("Earn 1 point per \$1 spent", color = ChmabaGray400, fontSize = 10.sp)
                }
                ChmabaBadge(
                    text = "${customer.points} pts",
                    tone = BadgeTone.Violet,
                )
            }

            Spacer(Modifier.height(14.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                PointsStepper(
                    value = adjustPoints,
                    onChange = { adjustPoints = it },
                )
                Spacer(Modifier.width(12.dp))
                ChmabaButton(
                    onClick = { },
                    text = "Add points",
                    modifier = Modifier.weight(1f),
                    variant = ButtonVariant.Primary,
                )
            }

            Spacer(Modifier.height(12.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                QuickPoints("+10") { adjustPoints += 10 }
                QuickPoints("+50") { adjustPoints += 50 }
                QuickPoints("+100") { adjustPoints += 100 }
                QuickPoints("Redeem") { adjustPoints = 0 }
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Adjustments above the store limit are sent to the owner for approval.",
                color = ChmabaGray400,
                fontSize = 10.sp,
                lineHeight = 15.sp,
            )
        }

        Spacer(Modifier.height(16.dp))

        Text("Recent orders", color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(8.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            history.forEachIndexed { index, order ->
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
                        Text(order.number, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.ExtraBold)
                        Spacer(Modifier.height(2.dp))
                        Text(order.detail, color = ChmabaGray400, fontSize = 10.sp)
                    }
                    ChmabaBadge("Paid", BadgeTone.Green)
                    Spacer(Modifier.width(10.dp))
                    Text(order.total, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.ExtraBold)
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun Stat(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(ChmabaSurface)
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
            fontSize = 17.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
    }
}

/** −/+ stepper replacing the web's raw input + button. */
@Composable
private fun PointsStepper(value: Int, onChange: (Int) -> Unit) {
    Row(
        modifier = Modifier
            .width(132.dp)
            .height(44.dp)
            .clip(RoundedCornerShape(13.dp))
            .background(ChmabaSurface)
            .border(1.dp, Color(0xFFDFDFE8), RoundedCornerShape(13.dp)),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(42.dp)
                .clickable { onChange((value - 10).coerceAtLeast(0)) },
            contentAlignment = Alignment.Center,
        ) {
            Icon(ChmabaIcons.Minus, contentDescription = "Decrease", tint = ChmabaGray900, modifier = Modifier.size(16.dp))
        }
        Text(
            value.toString(),
            color = ChmabaGray900,
            fontSize = 14.sp,
            fontWeight = FontWeight.ExtraBold,
            modifier = Modifier.weight(1f),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        Box(
            modifier = Modifier
                .size(42.dp)
                .clickable { onChange(value + 10) },
            contentAlignment = Alignment.Center,
        ) {
            Icon(ChmabaIcons.Plus, contentDescription = "Increase", tint = ChmabaGray900, modifier = Modifier.size(16.dp))
        }
    }
}

@Composable
private fun QuickPoints(label: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(99.dp))
            .background(ChmabaLavender)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(label, color = ChmabaBlue, fontSize = 10.5.sp, fontWeight = FontWeight.Bold)
    }
}
