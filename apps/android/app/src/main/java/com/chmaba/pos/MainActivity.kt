package com.chmaba.pos

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.chmaba.pos.data.auth.DeepLink
import com.chmaba.pos.data.auth.SessionStore
import com.chmaba.pos.data.auth.isAuthDeepLink
import com.chmaba.pos.data.auth.parseAuthDeepLink
import com.chmaba.pos.ui.AppRoot
import com.chmaba.pos.ui.theme.ChmabaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Must run before the composition reads the saved session.
        SessionStore.init(this)
        captureAuthDeepLink(intent)
        setContent {
            ChmabaTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    AppRoot()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        captureAuthDeepLink(intent)
    }

    /**
     * The Google round-trip returns through `chmaba://auth#…`. The token is put
     * on [DeepLink] so the composition can open the session.
     */
    private fun captureAuthDeepLink(intent: Intent?) {
        val data = intent?.data ?: return
        if (!isAuthDeepLink(data)) return
        val (token, error) = parseAuthDeepLink(data)
        DeepLink.pendingToken = token
        DeepLink.pendingError = error
    }
}
