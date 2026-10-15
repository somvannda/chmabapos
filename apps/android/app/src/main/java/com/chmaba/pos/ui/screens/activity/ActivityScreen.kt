package com.chmaba.pos.ui.screens.activity

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.audit.AuditEntryDto
import com.chmaba.pos.data.audit.AuditRepository
import com.chmaba.pos.data.audit.localStamp
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.LoadStateNotice
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaSurface
import kotlinx.coroutines.launch

private val ActivityBg = Color(0xFFF7F7FA)

/**
 * What the team changed, newest first.
 *
 * Every row comes from `GET /audit-logs`, which returns the same entries the web's Activity page
 * shows. The details map is per-action - an inventory adjustment carries a product and a quantity,
 * a settings change carries rules - so it is rendered as the key/value pairs the API sent rather
 * than mapped onto columns that would be blank for most actions.
 */
@Composable
fun ActivityScreen(
    modifier: Modifier = Modifier,
    viewModel: ActivityViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    val entries = (viewModel.state as? LoadState.Ready)?.data.orEmpty()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(ActivityBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            "Activity",
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            "Recent changes made by your team across the workspace.",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
        )

        Spacer(Modifier.height(16.dp))

        entries.forEach { entry ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(ChmabaSurface)
                    .padding(horizontal = 14.dp, vertical = 12.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    ChmabaBadge(text = entry.action, tone = BadgeTone.Blue)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        entry.entityType.orEmpty(),
                        color = ChmabaGray400,
                        fontSize = 10.sp,
                    )
                }
                Spacer(Modifier.height(6.dp))
                Text(
                    (entry.actor ?: "System") + "  ·  " + localStamp(entry.createdAt),
                    color = ChmabaGray500,
                    fontSize = 10.5.sp,
                    fontWeight = FontWeight.Bold,
                )
                val details = entry.details.orEmpty().entries
                    .joinToString("   ·   ") { it.key + ": " + it.value }
                if (details.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(details, color = ChmabaGray900, fontSize = 11.5.sp, lineHeight = 16.sp)
                }
            }
            Spacer(Modifier.height(8.dp))
        }

        Box(Modifier.fillMaxWidth()) {
            LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading activity…",
                failedTitle = "Could not load activity",
                onRetry = viewModel::load,
            )
        }
    }
}

class ActivityViewModel(
    private val repository: AuditRepository = AuditRepository(),
) : ViewModel() {
    var state: LoadState<List<AuditEntryDto>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.entries())
            } catch (problem: Exception) {
                LoadState.Failed(
                    com.chmaba.pos.data.readableMessage(problem) ?: "Could not load activity",
                )
            }
        }
    }
}
