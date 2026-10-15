package com.chmaba.pos.ui.screens.splash

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.ChmabaLogo
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaLime
import kotlinx.coroutines.delay

private val SplashInk = Color(0xFF17181C)
private val SplashMuted = Color(0xFFA9AAB2)
private val SplashFaint = Color(0xFF6F7078)

/**
 * Three-stage launch sequence, matching the prototype (splash / splash-2 /
 * splash-3 in apps/android/prototype/mobile-ui.html):
 *
 *  1. brand reveal
 *  2. what the product does (three feature marks)
 *  3. session check with an indeterminate bar
 *
 * Each stage holds for [stageMillis] then hands off to [onFinished].
 */
@Composable
fun SplashScreen(
    modifier: Modifier = Modifier,
    stageMillis: Long = 1500L,
    onFinished: () -> Unit,
) {
    var stage by remember { mutableIntStateOf(0) }

    LaunchedEffect(Unit) {
        while (stage < 2) {
            delay(stageMillis)
            stage += 1
        }
        delay(stageMillis)
        onFinished()
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(SplashInk),
        contentAlignment = Alignment.Center,
    ) {
        // Decorative rings, clipped by the parent like the prototype's overflow:hidden.
        Box(
            Modifier
                .align(Alignment.TopEnd)
                .offset(x = 70.dp, y = 60.dp)
                .size(230.dp)
                .border(34.dp, ChmabaLime.copy(alpha = 0.10f), CircleShape),
        )
        Box(
            Modifier
                .align(Alignment.BottomStart)
                .offset(x = (-60).dp, y = 70.dp)
                .size(250.dp)
                .background(
                    Brush.radialGradient(listOf(ChmabaLime.copy(alpha = 0.10f), Color.Transparent)),
                    CircleShape,
                ),
        )

        AnimatedContent(
            targetState = stage,
            transitionSpec = {
                (fadeIn(tween(300)) + scaleIn(tween(300), initialScale = 0.94f)) togetherWith
                    (fadeOut(tween(200)) + scaleOut(tween(200), targetScale = 1.02f))
            },
            label = "splash-stage",
        ) { current ->
            when (current) {
                0 -> StageBrand()
                1 -> StagePromise()
                else -> StageLoading()
            }
        }
    }
}

@Composable
private fun StageBrand() {
    var shown by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { shown = true }
    val scale by animateFloatAsState(
        targetValue = if (shown) 1f else 0.86f,
        animationSpec = tween(600),
        label = "brand-scale",
    )
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.scale(scale)) {
            ChmabaLogo(onDark = true, wordmark = false, chipSize = 56.dp)
        }
        Spacer(Modifier.height(18.dp))
        Text(
            text = "chmaba",
            color = Color.White,
            fontSize = 30.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.055).sp,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = "Your store, in a better flow.",
            color = SplashMuted,
            fontSize = 12.sp,
        )
    }
}

@Composable
private fun StagePromise() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(horizontal = 24.dp),
    ) {
        Text(
            text = "BUILT FOR BUSY COUNTERS",
            color = ChmabaLime,
            fontSize = 11.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 0.16.sp,
        )
        Spacer(Modifier.height(14.dp))
        Text(
            text = "One workspace.\nEvery moving part.",
            color = Color.White,
            fontSize = 26.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.055).sp,
            textAlign = TextAlign.Center,
            lineHeight = 30.sp,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            text = "Sales, stock and your whole team in one calm place.",
            color = SplashMuted,
            fontSize = 12.sp,
            textAlign = TextAlign.Center,
            lineHeight = 18.sp,
        )
        Spacer(Modifier.height(26.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(18.dp)) {
            FeatureMark(ChmabaIcons.Cart, "Fast sales entry")
            FeatureMark(ChmabaIcons.Boxes, "Live inventory")
            FeatureMark(ChmabaIcons.BarChart, "Clear reports")
        }
    }
}

@Composable
private fun FeatureMark(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.width(78.dp),
    ) {
        Icon(icon, contentDescription = null, tint = ChmabaLime, modifier = Modifier.size(24.dp))
        Spacer(Modifier.height(8.dp))
        Text(
            text = label,
            color = SplashMuted,
            fontSize = 10.sp,
            textAlign = TextAlign.Center,
            lineHeight = 13.sp,
        )
    }
}

@Composable
private fun StageLoading() {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        ChmabaLogo(onDark = true, wordmark = false, chipSize = 44.dp)
        Spacer(Modifier.height(16.dp))
        Text(
            text = "Preparing your workspace…",
            color = Color(0xFFE4E4E8),
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(14.dp))
        LinearProgressIndicator(
            modifier = Modifier
                .width(132.dp)
                .height(3.dp)
                .clip(CircleShape),
            color = ChmabaLime,
            trackColor = Color.White.copy(alpha = 0.16f),
        )
        Spacer(Modifier.height(12.dp))
        Text(
            text = "Checking your session and your workspace",
            color = SplashFaint,
            fontSize = 10.5.sp,
            textAlign = TextAlign.Center,
        )
    }
}
