package com.chmaba.pos.ui.screens.plans

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import androidx.lifecycle.viewmodel.compose.viewModel
import com.chmaba.pos.data.plans.BillingCycle
import com.chmaba.pos.data.plans.PlanDto
import com.chmaba.pos.data.plans.PlansRepository
import com.chmaba.pos.data.plans.featuredCode
import com.chmaba.pos.data.plans.isFree
import com.chmaba.pos.data.plans.priceLabel
import com.chmaba.pos.data.plans.totalFor
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaGreen
import com.chmaba.pos.ui.theme.ChmabaSurface
import kotlinx.coroutines.launch

private val PlansBg = Color(0xFFF7F7FA)
private val LimeCards = Color(0xFFC4F27C)
private val LimeInk = Color(0xFF172015)
private val LimeMuted = Color(0xFF40522F)
private val PlanBorder = Color(0xFFE9E9EF)

sealed interface PlansUiState {
    data object Loading : PlansUiState
    data class Error(val message: String) : PlansUiState
    data class Ready(val plans: List<PlanDto>) : PlansUiState
}

/**
 * Loads the public plans list. No hardcoded prices or feature bullets: both come
 * from `GET /v1/plans`, the same endpoint the web app uses.
 */
class PlansViewModel(
    private val repository: PlansRepository = PlansRepository(),
) : ViewModel() {

    var state: PlansUiState by mutableStateOf(PlansUiState.Loading)
        private set

    var cycle: BillingCycle by mutableStateOf(BillingCycle.Monthly)
        private set

    var selectedCode: String? by mutableStateOf(null)
        private set

    init {
        load()
    }

    fun load() {
        state = PlansUiState.Loading
        viewModelScope.launch {
            state = try {
                val plans = repository.plans()
                if (selectedCode == null) selectedCode = plans.featuredCode()
                PlansUiState.Ready(plans)
            } catch (error: Exception) {
                PlansUiState.Error(error.message ?: "Could not load plans")
            }
        }
    }

    fun selectCycle(next: BillingCycle) {
        cycle = next
    }

    fun selectPlan(code: String) {
        selectedCode = code
    }
}

@Composable
fun PlansScreen(
    modifier: Modifier = Modifier,
    onBack: (() -> Unit)? = null,
    onChoosePlan: (String) -> Unit = {},
    viewModel: PlansViewModel = viewModel(),
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(PlansBg),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
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
            }
            Column(Modifier.weight(1f)) {
                Text(
                    "Plans",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text("Live pricing from Chmaba.", color = ChmabaGray500, fontSize = 12.5.sp)
            }
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(ChmabaSurface)
                    .clickable { viewModel.load() },
                contentAlignment = Alignment.Center,
            ) {
                Icon(ChmabaIcons.Refresh, contentDescription = "Reload", tint = ChmabaGray500, modifier = Modifier.size(17.dp))
            }
        }

        when (val state = viewModel.state) {
            is PlansUiState.Loading -> Centered {
                CircularProgressIndicator(color = Color(0xFF6957F5), strokeWidth = 3.dp)
                Spacer(Modifier.height(14.dp))
                Text("Loading plans…", color = ChmabaGray500, fontSize = 12.sp)
            }

            is PlansUiState.Error -> Centered {
                Box(
                    modifier = Modifier
                        .size(46.dp)
                        .clip(RoundedCornerShape(15.dp))
                        .background(Color(0xFFFFF0EE)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(ChmabaIcons.Alert, contentDescription = null, tint = Color(0xFFC2564B), modifier = Modifier.size(22.dp))
                }
                Spacer(Modifier.height(14.dp))
                Text("Could not load plans", color = ChmabaGray900, fontSize = 14.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.height(6.dp))
                Text(
                    state.message,
                    color = ChmabaGray400,
                    fontSize = 11.5.sp,
                    lineHeight = 17.sp,
                )
                Spacer(Modifier.height(16.dp))
                ChmabaButton(
                    onClick = { viewModel.load() },
                    text = "Try again",
                    variant = ButtonVariant.Primary,
                    size = ButtonSize.Large,
                    leadingIcon = { Icon(ChmabaIcons.Refresh, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp)) },
                )
                Spacer(Modifier.height(10.dp))
                Text(
                    "Expects the API at 10.0.2.2:8001 from the emulator.",
                    color = ChmabaGray400,
                    fontSize = 10.sp,
                )
            }

            is PlansUiState.Ready -> PlansContent(
                plans = state.plans,
                cycle = viewModel.cycle,
                selectedCode = viewModel.selectedCode,
                onSelectCycle = viewModel::selectCycle,
                onSelectPlan = viewModel::selectPlan,
                onChoosePlan = onChoosePlan,
            )
        }
    }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) { content() }
}

@Composable
private fun PlansContent(
    plans: List<PlanDto>,
    cycle: BillingCycle,
    selectedCode: String?,
    onSelectCycle: (BillingCycle) -> Unit,
    onSelectPlan: (String) -> Unit,
    onChoosePlan: (String) -> Unit,
) {
    val featured = plans.featuredCode()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
    ) {
        Text(
            "Billing cycle",
            color = ChmabaGray900,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(8.dp))

        BillingCycle.entries.forEach { entry ->
            CycleRow(
                cycle = entry,
                active = entry == cycle,
                onClick = { onSelectCycle(entry) },
            )
            Spacer(Modifier.height(8.dp))
        }

        Spacer(Modifier.height(10.dp))
        Text(
            "Choose a plan",
            color = ChmabaGray900,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(8.dp))

        plans.forEach { plan ->
            PlanCard(
                plan = plan,
                cycle = cycle,
                active = plan.code == selectedCode,
                featured = plan.code == featured,
                onClick = { onSelectPlan(plan.code) },
            )
            Spacer(Modifier.height(12.dp))
        }

        val chosen = plans.firstOrNull { it.code == selectedCode }
        ChmabaButton(
            onClick = { selectedCode?.let(onChoosePlan) },
            text = when {
                chosen == null -> "Choose a plan"
                chosen.isFree() -> "Continue with ${chosen.name}"
                else -> "Continue with ${chosen.name}"
            },
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = selectedCode != null,
        )

        Spacer(Modifier.height(12.dp))
        Text(
            "Money from your counter sales goes straight to your own ABA, Bakong or ChmabaPay account — Chmaba never holds or settles it. We only bill you for your Chmaba subscription.",
            color = ChmabaGray400,
            fontSize = 10.sp,
            lineHeight = 15.sp,
        )
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun CycleRow(cycle: BillingCycle, active: Boolean, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(13.dp))
            .background(ChmabaSurface)
            .clickable(onClick = onClick)
            .padding(horizontal = 13.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(18.dp)
                .clip(CircleShape)
                .background(if (active) Color(0xFF6957F5) else ChmabaSurface),
            contentAlignment = Alignment.Center,
        ) {
            if (active) {
                Icon(ChmabaIcons.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(11.dp))
            }
        }
        Spacer(Modifier.width(11.dp))
        Column(Modifier.weight(1f)) {
            Text(cycle.label, color = ChmabaGray900, fontSize = 12.5.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(2.dp))
            Text(cycle.billedLabel, color = ChmabaGray400, fontSize = 10.5.sp)
        }
        if (cycle.badge != null) {
            ChmabaBadge(cycle.badge!!, BadgeTone.Green)
        }
    }
}

@Composable
private fun PlanCard(
    plan: PlanDto,
    cycle: BillingCycle,
    active: Boolean,
    featured: Boolean,
    onClick: () -> Unit,
) {
    val background = if (featured) LimeCards else ChmabaSurface
    val titleColor = if (featured) LimeMuted else Color(0xFF6957F5)
    val bodyColor = if (featured) Color(0xFF3E5130) else ChmabaGray400
    val priceColor = if (featured) LimeInk else ChmabaGray900

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(background)
            .clickable(onClick = onClick)
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(plan.name, color = titleColor, fontSize = 12.5.sp, fontWeight = FontWeight.ExtraBold)
            if (featured) {
                Spacer(Modifier.width(8.dp))
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(99.dp))
                        .background(Color(0xFF17181C))
                        .padding(horizontal = 8.dp, vertical = 3.dp),
                ) {
                    Text("MOST POPULAR", color = LimeCards, fontSize = 8.5.sp, fontWeight = FontWeight.ExtraBold)
                }
            }
            Spacer(Modifier.weight(1f))
            Box(
                modifier = Modifier
                    .size(20.dp)
                    .clip(CircleShape)
                    .background(if (active) (if (featured) Color(0xFF17181C) else Color(0xFF6957F5)) else Color.Transparent),
                contentAlignment = Alignment.Center,
            ) {
                if (active) {
                    Icon(
                        ChmabaIcons.Check,
                        contentDescription = null,
                        tint = if (featured) LimeCards else Color.White,
                        modifier = Modifier.size(12.dp),
                    )
                }
            }
        }

        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                plan.priceLabel(cycle),
                color = priceColor,
                fontSize = 30.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.06).sp,
            )
            if (!plan.isFree()) {
                Spacer(Modifier.width(4.dp))
                Text("/mo", color = bodyColor, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
            }
        }
        plan.totalFor(cycle)?.let { total ->
            Spacer(Modifier.height(3.dp))
            Text("\$$total ${cycle.billedLabel}", color = bodyColor, fontSize = 10.sp)
        }
        plan.description?.let { description ->
            Spacer(Modifier.height(6.dp))
            Text(description, color = bodyColor, fontSize = 11.sp, lineHeight = 16.sp)
        }

        if (plan.marketingFeatures.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            plan.marketingFeatures.forEach { feature ->
                Row(verticalAlignment = Alignment.Top) {
                    Icon(
                        ChmabaIcons.Check,
                        contentDescription = null,
                        tint = if (featured) Color(0xFF4D7835) else ChmabaGreen,
                        modifier = Modifier.size(14.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        feature,
                        color = if (featured) Color(0xFF3E5130) else ChmabaGray500,
                        fontSize = 11.5.sp,
                        lineHeight = 16.sp,
                    )
                }
                Spacer(Modifier.height(7.dp))
            }
        }
    }
}
