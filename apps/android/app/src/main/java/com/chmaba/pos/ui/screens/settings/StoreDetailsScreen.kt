package com.chmaba.pos.ui.screens.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.data.auth.AuthRepository
import com.chmaba.pos.data.auth.StoreDto
import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.readableMessage
import com.chmaba.pos.data.store.StoreSettingsRepository
import com.chmaba.pos.data.store.StoreUpdateDto
import com.chmaba.pos.data.store.taxRateProblem
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaRed
import kotlinx.coroutines.launch

/**
 * The settings screens' own background. SettingsScreen keeps its copy private to its file, and a
 * second constant here is cheaper than a shared one for the sake of two screens.
 */
private val StoreDetailsBg = Color(0xFFF7F7FA)

/**
 * The store's own details, editable.
 *
 * This screen exists because the README used to say the API had no endpoint behind it. It has one:
 * `PATCH /stores/{id}` takes a name, an address, a phone and an email (`StoreUpdateRequest`), and
 * the web POS edits exactly these. What was missing was this app ever calling it, so the row in
 * Settings raised a notice instead of opening anything.
 *
 * The store is read back from the server rather than kept in the session: nothing else on the
 * client holds an address, a phone or an email, and a half-remembered copy would be worse than a
 * moment's wait. What is saved is what the server answered with, not what was typed.
 */
@Composable
fun StoreDetailsScreen(
    modifier: Modifier = Modifier,
    auth: AuthRepository = remember { AuthRepository() },
    stores: StoreSettingsRepository = remember { StoreSettingsRepository() },
    onBack: () -> Unit = {},
    /** The store as the server now holds it, so the shell can update the header. */
    onSaved: (StoreDto) -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf<String?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var name by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var taxRate by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        try {
            val store = auth.currentStore()
            name = store?.name.orEmpty()
            address = store?.address.orEmpty()
            phone = store?.phone.orEmpty()
            email = store?.email.orEmpty()
            taxRate = store?.serviceTaxRate.orEmpty()
        } catch (problem: Exception) {
            failed = readableMessage(problem) ?: "Could not read the store"
        } finally {
            loading = false
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(StoreDetailsBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text("Store details", color = ChmabaGray900, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(4.dp))
        Text(
            "What this store is called, and how a customer reaches it.",
            color = ChmabaGray500,
            fontSize = 11.sp,
        )
        Spacer(Modifier.height(16.dp))

        if (loading) {
            Text("Reading the store…", color = ChmabaGray400, fontSize = 12.sp)
            return@Column
        }

        Field("Store name", name, { name = it })
        Field("Address", address, { address = it })
        Field("Phone", phone, { phone = it }, KeyboardType.Phone)
        Field("Email", email, { email = it }, KeyboardType.Email)
        Field("Service tax rate (%)", taxRate, { taxRate = it }, KeyboardType.Decimal)

        // A wrong rate is a wrong price on the next receipt, so it is caught here rather than by a
        // 422 naming a field the person typing has never seen.
        val rateProblem = taxRateProblem(taxRate)
        if (rateProblem != null) {
            Text(rateProblem, color = ChmabaRed, fontSize = 11.5.sp)
            Spacer(Modifier.height(10.dp))
        }

        failed?.let {
            Text(it, color = ChmabaRed, fontSize = 11.5.sp)
            Spacer(Modifier.height(10.dp))
        }
        notice?.let {
            Text(it, color = ChmabaGray500, fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(10.dp))
        }

        ChmabaButton(
            onClick = {
                // A blank name is refused by the API, so it is not sent: the button says why
                // instead of the server answering 422 to something the reader could not see.
                if (!saving && name.isNotBlank() && rateProblem == null) {
                    saving = true
                    failed = null
                    notice = null
                    scope.launch {
                        try {
                            val saved = stores.update(
                                StoreUpdateDto(
                                    name = name.trim(),
                                    address = address.trim(),
                                    phone = phone.trim(),
                                    email = email.trim(),
                                    serviceTaxRate = taxRate.trim(),
                                ),
                            )
                            name = saved.name ?: name
                            taxRate = saved.serviceTaxRate ?: taxRate
                            // The till charges this rate, so a saved one is in force at once rather
                            // than at the next sign-in.
                            Session.serviceTaxRate = saved.serviceTaxRate ?: Session.serviceTaxRate
                            notice = "Saved."
                            onSaved(saved)
                        } catch (problem: Exception) {
                            failed = readableMessage(problem) ?: "Could not save the store"
                        } finally {
                            saving = false
                        }
                    }
                }
            },
            text = if (saving) "Saving…" else "Save",
            modifier = Modifier.fillMaxWidth(),
            size = ButtonSize.Large,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "Back to settings",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onBack)
                .padding(vertical = 12.dp),
        )
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    keyboard: KeyboardType = KeyboardType.Text,
) {
    Text(label, color = ChmabaGray500, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(4.dp))
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        modifier = Modifier.fillMaxWidth(),
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
    )
    Spacer(Modifier.height(12.dp))
}
