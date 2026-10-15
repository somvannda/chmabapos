package com.chmaba.pos.ui.screens.team

import androidx.compose.foundation.background
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
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.team.MembershipDto
import com.chmaba.pos.data.team.TeamRepository
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.LoadStateNotice
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaSurface
import kotlinx.coroutines.launch

private val TeamBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)

/**
 * Who can sign in to this company, and in what role.
 *
 * Every row comes from `GET /team` and nothing is inferred - that endpoint returns one membership
 * per person, which on this company is the owner alone, so the screen shows one row rather than a
 * mock-up's worth of staff.
 *
 * There is deliberately no invite button. `POST /team/invitations` exists on the API and is not
 * wired here, and a control that only raised a notice is the kind of decoration this app has been
 * removing; the More list says what this screen holds rather than what it might.
 */
@Composable
fun TeamScreen(
    modifier: Modifier = Modifier,
    viewModel: TeamViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    val members = (viewModel.state as? LoadState.Ready)?.data.orEmpty()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(TeamBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            "Team",
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(2.dp))
        Text("Who can sign in, and what they may do.", color = ChmabaGray500, fontSize = 12.5.sp)

        Spacer(Modifier.height(16.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            members.forEachIndexed { index, member ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(11.dp))
                            .background(ChmabaLavender),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            initialsOf(member),
                            color = ChmabaBlue,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.ExtraBold,
                        )
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            nameOf(member),
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(member.user?.email.orEmpty(), color = ChmabaGray400, fontSize = 10.sp)
                        Spacer(Modifier.height(2.dp))
                        Text(
                            reachOf(member),
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        ChmabaBadge(
                            text = roleLabel(member.role),
                            tone = if (member.role == "owner") BadgeTone.Blue else BadgeTone.Neutral,
                        )
                        Spacer(Modifier.height(4.dp))
                        ChmabaBadge(
                            text = if (member.status == "active") {
                                "Active"
                            } else {
                                member.status.replaceFirstChar { it.uppercase() }
                            },
                            tone = if (member.status == "active") BadgeTone.Blue else BadgeTone.Neutral,
                        )
                    }
                }
            }
            LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading the team…",
                failedTitle = "Could not load the team",
                onRetry = viewModel::load,
            )
        }
    }
}

private fun nameOf(member: MembershipDto): String =
    member.user?.fullName?.takeIf { it.isNotBlank() }
        ?: member.user?.email
        ?: "Unnamed member"

/** "Owner", not "owner": the API's role key is lowercase and this is a label. */
private fun roleLabel(role: String): String =
    if (role.isBlank()) "—" else role.replaceFirstChar { it.uppercase() }

/**
 * Which stores this member reaches. The payload carries store ids, not names, and the app has no
 * member-to-store lookup, so this counts them rather than naming one it cannot resolve.
 */
private fun reachOf(member: MembershipDto): String = when (member.storeIds.size) {
    0 -> "All stores"
    1 -> "1 store"
    else -> member.storeIds.size.toString() + " stores"
}

private fun initialsOf(member: MembershipDto): String {
    val parts = nameOf(member).split(" ", ".", "@", "_").filter { it.isNotBlank() }
    return parts.take(2).map { it.first().uppercase() }.joinToString("").ifEmpty { "?" }
}

class TeamViewModel(
    private val repository: TeamRepository = TeamRepository(),
) : ViewModel() {
    var state: LoadState<List<MembershipDto>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.members())
            } catch (problem: Exception) {
                LoadState.Failed(
                    com.chmaba.pos.data.readableMessage(problem) ?: "Could not load the team",
                )
            }
        }
    }
}
