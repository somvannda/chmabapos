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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
    /**
     * The workspace's own plan features, as `/workspaces/current` reports them. Listed
     * rather than offered as switches: a plan is changed through billing, not here, and
     * the switches this replaces changed nothing at all.
     */
    planFeatures: List<String> = emptyList(),
    onOpenSection: (String) -> Unit = {},
    onSignOut: () -> Unit = {},
) {
    // These describe what the web app owns. No value is asserted here, because this
    // screen reads none of it: it used to print a tax rate, a receipt width and
    // hardware states that nothing on this device had measured.
    val storeRows = listOf(
        SettingsRow("Store details", "Name, address, receipts", ChmabaIcons.Store),
        // Both live on the Store details form, which this app edits through PATCH /stores/{id}.
        // Saying they were "set in the web app" was false, and tapping them claimed the screen did
        // not exist either - so the two settings the app *can* edit were the two it denied.
        SettingsRow("Currency & exchange rates", "Edit in Store details", ChmabaIcons.Dollar),
        SettingsRow("Tax", "Edit in Store details", ChmabaIcons.Receipt),
    )
    val sellingRows = listOf(
        SettingsRow("Payment methods", "Set in the web app", ChmabaIcons.CreditCard),
        SettingsRow("Receipts & printing", "Set in the web app", ChmabaIcons.Printer),
        SettingsRow("Customer display", "Set in the web app", ChmabaIcons.Monitor),
    )
    // What this app can and cannot reach on the device. Camera scanning is real; there
    // is no printer or cash-drawer support, so neither offers a status or a Pair button.
    val hardwareRows = listOf(
        SettingsRow("Receipt printer", "Not supported in this app yet", ChmabaIcons.Printer),
        SettingsRow("Barcode scanner", "Uses the device camera", ChmabaIcons.Scan, "Ready", BadgeTone.Green),
        SettingsRow("Cash drawer", "Not supported in this app yet", ChmabaIcons.Wallet),
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

        SectionHeading("In your plan")
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            if (planFeatures.isEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "No features are enabled for this plan.",
                        color = ChmabaGray400,
                        fontSize = 10.5.sp,
                    )
                }
            }
            planFeatures.forEachIndexed { index, feature ->
                if (index > 0) Divider()
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RowIcon(ChmabaIcons.Check)
                    Spacer(Modifier.width(12.dp))
                    Text(
                        // Taken from the workspace's own plan_features, so the list
                        // tracks the server without a second copy of the feature
                        // catalog living in the app.
                        feature.replace('_', ' ').replaceFirstChar { it.uppercase() },
                        color = ChmabaGray900,
                        fontSize = 12.5.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
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
