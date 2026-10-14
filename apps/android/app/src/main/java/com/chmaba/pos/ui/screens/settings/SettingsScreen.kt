package com.chmaba.pos.ui.screens.settings

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
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
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
import androidx.compose.ui.graphics.vector.ImageVector
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

private val SettingsBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)

private data class SettingsRow(
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val status: String? = null,
    val tone: BadgeTone = BadgeTone.Neutral,
)

/**
 * Store settings, grouped the same way as the web settings tree
 * (apps/web/src/features/settings.jsx): store, selling, feature packs, hardware.
 */
@Composable
fun SettingsScreen(
    modifier: Modifier = Modifier,
    storeName: String = "Your store",
    onOpenSection: (String) -> Unit = {},
    onSignOut: () -> Unit = {},
) {
    var tablesPack by remember { mutableStateOf(true) }
    var serialsPack by remember { mutableStateOf(false) }
    var heldOrdersPack by remember { mutableStateOf(true) }

    val storeRows = listOf(
        SettingsRow("Store details", "Name, address, receipts", ChmabaIcons.Store),
        SettingsRow("Currency & exchange rates", "USD base · KHR, THB", ChmabaIcons.Dollar),
        SettingsRow("Tax", "Service tax 10% · exclusive", ChmabaIcons.Receipt),
    )
    val sellingRows = listOf(
        SettingsRow("Payment methods", "Cash, KHQR enabled", ChmabaIcons.CreditCard),
        SettingsRow("Receipts & printing", "Thermal 80mm · auto-print on", ChmabaIcons.Printer),
        SettingsRow("Customer display", "External screen snapshot", ChmabaIcons.Monitor),
    )
    val hardwareRows = listOf(
        SettingsRow("Receipt printer", "Not connected", ChmabaIcons.Printer, "Pair", BadgeTone.Neutral),
        SettingsRow("Barcode scanner", "Use camera", ChmabaIcons.Scan, "Ready", BadgeTone.Green),
        SettingsRow("Cash drawer", "Pulse on cash tender", ChmabaIcons.Wallet, "Off", BadgeTone.Neutral),
    )

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(SettingsBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            "Settings",
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(2.dp))
        Text(storeName, color = ChmabaGray500, fontSize = 12.5.sp)

        SectionHeading("Store")
        SettingsGroup(storeRows, onOpenSection)

        SectionHeading("Selling")
        SettingsGroup(sellingRows, onOpenSection)

        SectionHeading("Feature packs")
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            SwitchRow(
                title = "Tables pack",
                subtitle = "Floor map, seats, courses",
                icon = ChmabaIcons.Users,
                checked = tablesPack,
                onChange = { tablesPack = it },
            )
            Divider()
            SwitchRow(
                title = "Serials & warranty",
                subtitle = "IMEI, condition grading",
                icon = ChmabaIcons.Tag,
                checked = serialsPack,
                onChange = { serialsPack = it },
            )
            Divider()
            SwitchRow(
                title = "Held orders",
                subtitle = "Park and resume tickets",
                icon = ChmabaIcons.Archive,
                checked = heldOrdersPack,
                onChange = { heldOrdersPack = it },
            )
        }

        SectionHeading("Hardware")
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            hardwareRows.forEachIndexed { index, row ->
                if (index > 0) Divider()
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpenSection(row.title) }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RowIcon(row.icon)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(row.title, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(2.dp))
                        Text(row.subtitle, color = ChmabaGray400, fontSize = 10.sp)
                    }
                    if (row.status != null) {
                        ChmabaBadge(row.status, row.tone)
                    }
                }
            }
        }

        Spacer(Modifier.height(18.dp))

        ChmabaButton(
            onClick = onSignOut,
            text = "Sign out",
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Danger,
            size = ButtonSize.Large,
        )
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun SectionHeading(text: String) {
    Spacer(Modifier.height(18.dp))
    Text(
        text.uppercase(),
        color = ChmabaGray400,
        fontSize = 9.5.sp,
        fontWeight = FontWeight.ExtraBold,
        letterSpacing = 1.1.sp,
    )
    Spacer(Modifier.height(8.dp))
}

@Composable
private fun Divider() {
    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
}

@Composable
private fun RowIcon(icon: ImageVector) {
    Box(
        modifier = Modifier
            .size(34.dp)
            .clip(RoundedCornerShape(11.dp))
            .background(ChmabaLavender),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = ChmabaBlue, modifier = Modifier.size(17.dp))
    }
}

@Composable
private fun SettingsGroup(rows: List<SettingsRow>, onOpen: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(ChmabaSurface),
    ) {
        rows.forEachIndexed { index, row ->
            if (index > 0) Divider()
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onOpen(row.title) }
                    .padding(horizontal = 16.dp, vertical = 13.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RowIcon(row.icon)
                Spacer(Modifier.width(12.dp))
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

@Composable
private fun SwitchRow(
    title: String,
    subtitle: String,
    icon: ImageVector,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onChange(!checked) }
            .padding(horizontal = 16.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RowIcon(icon)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(2.dp))
            Text(subtitle, color = ChmabaGray400, fontSize = 10.sp)
        }
        Spacer(Modifier.width(10.dp))
        Switch(
            checked = checked,
            onCheckedChange = onChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = ChmabaBlue,
                uncheckedThumbColor = Color.White,
                uncheckedTrackColor = ChmabaGray400,
            ),
        )
    }
}
