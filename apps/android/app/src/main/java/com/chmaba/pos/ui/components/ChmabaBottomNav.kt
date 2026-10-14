package com.chmaba.pos.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaSurface

/** Tabs in the bottom bar. "More" hosts everything that isn't a primary surface. */
enum class NavTab { Home, Pos, Orders, More }

data class BottomNavItem(
    val tab: NavTab,
    val icon: ImageVector,
    val label: String,
)

/**
 * Bottom navigation with an unmistakable active state, mirroring the prototype:
 * a violet pill behind the active icon, a purple indicator bar on the top edge,
 * a heavier label, and a press-down scale. Every state change is animated.
 */
@Composable
fun ChmabaBottomNav(
    items: List<BottomNavItem>,
    selected: NavTab,
    onSelect: (NavTab) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(64.dp)
            .background(ChmabaSurface),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        items.forEach { item ->
            NavBarItem(
                item = item,
                active = item.tab == selected,
                onClick = { onSelect(item.tab) },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun NavBarItem(
    item: BottomNavItem,
    active: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()

    val indicator by animateFloatAsState(
        targetValue = if (active) 1f else 0f,
        animationSpec = tween(durationMillis = 240),
        label = "nav-indicator",
    )
    val pill by animateFloatAsState(
        targetValue = if (active) 1f else 0f,
        animationSpec = tween(durationMillis = 180),
        label = "nav-pill",
    )
    val pressScale by animateFloatAsState(
        targetValue = if (pressed) 0.9f else 1f,
        animationSpec = tween(durationMillis = 120),
        label = "nav-press",
    )

    Column(
        modifier = modifier
            .height(64.dp)
            .clickable(
                interactionSource = interaction,
                indication = null,
                onClick = onClick,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Top,
    ) {
        Box(
            modifier = Modifier
                .width(30.dp)
                .height(3.dp)
                .graphicsLayer { scaleX = indicator; transformOrigin = androidx.compose.ui.graphics.TransformOrigin(0.5f, 0f) }
                .clip(RoundedCornerShape(bottomStart = 3.dp, bottomEnd = 3.dp))
                .background(ChmabaBlue),
        )
        Spacer(Modifier.height(7.dp))
        Box(
            modifier = Modifier
                .size(width = 40.dp, height = 26.dp)
                .graphicsLayer {
                    scaleX = pressScale
                    scaleY = pressScale
                }
                .clip(RoundedCornerShape(11.dp))
                .background(ChmabaLavender.copy(alpha = pill)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = item.icon,
                contentDescription = item.label,
                tint = if (active) ChmabaBlue else ChmabaGray400,
                modifier = Modifier.size(20.dp),
            )
        }
        Spacer(Modifier.height(2.dp))
        Text(
            text = item.label,
            fontSize = 9.sp,
            fontWeight = if (active) FontWeight.ExtraBold else FontWeight.Bold,
            color = if (active) ChmabaBlue else ChmabaGray400,
        )
    }
}

/** Hairline above the bar, matching the web shell. */
@Composable
fun NavDivider(modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(Color(0xFFE9E9EF)),
    )
}
