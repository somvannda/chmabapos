package com.chmaba.pos.ui.screens.help

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.runtime.remember
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
import com.chmaba.pos.data.support.SupportSectionDto
import com.chmaba.pos.data.support.SupportRepository
import com.chmaba.pos.ui.components.LoadStateNotice
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaSurface
import kotlinx.coroutines.launch

private val HelpBg = Color(0xFFF7F7FA)

/**
 * The guides, grouped by section, one article open at a time.
 *
 * Everything shown comes from `GET /support/articles`, which has already narrowed the corpus to
 * this company's vertical and this member's role. Nothing is summarised or rewritten - the steps
 * are the API's own copy, and they describe the POS rather than one client of it, which is why a
 * step can mention the web's sidebar.
 *
 * What is not here: the AI assistant. `POST /support/chat` and the starter prompts are real
 * endpoints and are not wired, so the screen says "Guides" rather than promising a conversation it
 * does not hold.
 */
@Composable
fun HelpScreen(
    modifier: Modifier = Modifier,
    viewModel: HelpViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    val sections = (viewModel.state as? LoadState.Ready)?.data.orEmpty()
    /** The article the reader opened, so only one set of steps is on screen at a time. */
    var openArticle by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(HelpBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text(
            "Help & support",
            color = ChmabaGray900,
            fontSize = 20.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            "Guides for this workspace.",
            color = ChmabaGray500,
            fontSize = 12.5.sp,
        )

        Spacer(Modifier.height(16.dp))

        sections.forEach { section ->
            Section(section, openArticle) { tapped ->
                openArticle = if (openArticle == tapped) null else tapped
            }
            Spacer(Modifier.height(10.dp))
        }

        if (sections.isEmpty()) {
            Box(Modifier.fillMaxWidth()) {
                LoadStateNotice(
                    state = viewModel.state,
                    loadingMessage = "Loading the guides…",
                    failedTitle = "Could not load the guides",
                    onRetry = viewModel::load,
                )
            }
        }
    }
}

@Composable
private fun Section(
    section: SupportSectionDto,
    openArticle: String?,
    onToggle: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(ChmabaSurface)
            .padding(horizontal = 16.dp, vertical = 14.dp),
    ) {
        Text(section.title, color = ChmabaGray900, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(2.dp))
        Text(section.blurb, color = ChmabaGray500, fontSize = 11.sp, lineHeight = 15.sp)

        section.articles.forEach { article ->
            val open = openArticle == article.id
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onToggle(article.id) },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    article.title,
                    color = if (open) ChmabaGray900 else ChmabaBlue,
                    fontSize = 12.sp,
                    fontWeight = if (open) FontWeight.Bold else FontWeight.Normal,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Text(if (open) "−" else "+", color = ChmabaGray400, fontSize = 13.sp)
            }
            if (open) {
                Spacer(Modifier.height(6.dp))
                article.steps.forEachIndexed { index, step ->
                    Text(
                        (index + 1).toString() + ".  " + step,
                        color = ChmabaGray900,
                        fontSize = 11.5.sp,
                        lineHeight = 16.sp,
                    )
                    Spacer(Modifier.height(4.dp))
                }
                article.tip?.takeIf { it.isNotBlank() }?.let { tip ->
                    Text("Tip: " + tip, color = ChmabaGray500, fontSize = 11.sp, lineHeight = 15.sp)
                }
            }
        }
    }
}

class HelpViewModel(
    private val repository: SupportRepository = SupportRepository(),
) : ViewModel() {
    var state: LoadState<List<SupportSectionDto>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.sections())
            } catch (problem: Exception) {
                LoadState.Failed(
                    com.chmaba.pos.data.readableMessage(problem) ?: "Could not load the guides",
                )
            }
        }
    }
}
