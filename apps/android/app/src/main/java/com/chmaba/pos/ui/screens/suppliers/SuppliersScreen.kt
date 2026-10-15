package com.chmaba.pos.ui.screens.suppliers

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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface

private val SuppliersBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)

/**
 * A supplier. `GET /suppliers` returns id, name, contact_name, phone, email and
 * is_active, and carries no payment terms — so there is no terms field here
 * rather than a placeholder that would look like data.
 */
data class Supplier(
    val name: String,
    val contact: String,
    val isActive: Boolean,
    val avatarColor: Color,
    val initials: String,
)

@Composable
fun SuppliersScreen(
    modifier: Modifier = Modifier,
    viewModel: com.chmaba.pos.ui.screens.store.SuppliersViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel(),
    onOpenSupplier: (String) -> Unit = {},
) {
    val suppliers = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    // Whether the add form is open; the form owns its own field values.
    var adding by remember { mutableStateOf(false) }

    if (adding) {
        AddSupplierDialog(
            creating = viewModel.creating,
            error = viewModel.createError,
            onDismiss = {
                viewModel.clearCreateError()
                adding = false
            },
            // The view model runs onCreated only on success, which closes the form.
            onCreate = { name, contact, phone, email ->
                viewModel.create(name, contact, phone, email) { adding = false }
            },
        )
    }
    var query by remember { mutableStateOf("") }
    val visible = if (query.isBlank()) suppliers else suppliers.filter {
        it.name.contains(query, ignoreCase = true) || it.contact.contains(query, ignoreCase = true)
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(SuppliersBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Suppliers",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text("Who you buy from, and at what cost.", color = ChmabaGray500, fontSize = 12.5.sp)
            }
            ChmabaButton(
                onClick = { adding = true },
                text = "Add",
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
                leadingIcon = {
                    Icon(ChmabaIcons.Plus, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                },
            )
        }

        Spacer(Modifier.height(16.dp))

        ChmabaTextField(
            value = query,
            onValueChange = { query = it },
            label = "Search",
            placeholder = "Search suppliers…",
        )

        Spacer(Modifier.height(6.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            visible.forEachIndexed { index, supplier ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpenSupplier(supplier.name) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(11.dp))
                            .background(supplier.avatarColor),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            supplier.initials,
                            color = Color(0xFF343039),
                            fontSize = 11.sp,
                            fontWeight = FontWeight.ExtraBold,
                        )
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(supplier.name, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(2.dp))
                        Text(
                            supplier.contact,
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    ChmabaBadge(
                        text = if (supplier.isActive) "Active" else "Inactive",
                        tone = if (supplier.isActive) BadgeTone.Blue else BadgeTone.Neutral,
                    )
                }
            }
            com.chmaba.pos.ui.components.LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading suppliers…",
                failedTitle = "Could not load suppliers",
                onRetry = { viewModel.load() },
            )
            if (visible.isEmpty() && viewModel.state is com.chmaba.pos.data.store.LoadState.Ready) {
                Text(
                    "No suppliers match that search.",
                    color = ChmabaGray400,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(20.dp),
                )
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

/**
 * The add-supplier form. Only a name is required.
 *
 * Creating a supplier needs the `purchasing` plan feature, so a plan without it
 * answers 403 — the server's message is shown here rather than swallowed, because
 * on a free plan that is the whole story.
 */
@Composable
private fun AddSupplierDialog(
    creating: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onCreate: (String, String?, String?, String?) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var contact by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = ChmabaSurface,
        title = {
            Text("Add supplier", color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        },
        text = {
            Column {
                ChmabaTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = "Name",
                    placeholder = "e.g. Bean Traders",
                )
                Spacer(Modifier.height(10.dp))
                ChmabaTextField(
                    value = contact,
                    onValueChange = { contact = it },
                    label = "Contact name",
                    placeholder = "Optional",
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
            }
        },
        confirmButton = {
            ChmabaButton(
                onClick = { onCreate(name, contact, phone, email) },
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
