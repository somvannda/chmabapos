package com.chmaba.pos.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900

/**
 * The loading and failed notice shared by the list screens, so a request that
 * fails names its reason and offers a retry instead of leaving an empty list
 * behind with no explanation.
 *
 * It renders nothing once the state is ready; the caller draws its own empty
 * state for "the request worked and there is nothing here".
 */
@Composable
fun LoadStateNotice(
    state: LoadState<*>,
    loadingMessage: String,
    failedTitle: String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    when (state) {
        is LoadState.Loading -> Text(
            loadingMessage,
            color = ChmabaGray400,
            fontSize = 12.sp,
            modifier = modifier.padding(20.dp),
        )

        is LoadState.Failed -> Column(modifier = modifier.padding(20.dp)) {
            Text(
                failedTitle,
                color = ChmabaGray900,
                fontSize = 13.sp,
                fontWeight = FontWeight.ExtraBold,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                state.message,
                color = ChmabaGray500,
                fontSize = 11.5.sp,
                lineHeight = 17.sp,
            )
            Spacer(Modifier.height(12.dp))
            ChmabaButton(
                onClick = onRetry,
                text = "Try again",
                variant = ButtonVariant.Outline,
                size = ButtonSize.Small,
            )
        }

        else -> Unit
    }
}
