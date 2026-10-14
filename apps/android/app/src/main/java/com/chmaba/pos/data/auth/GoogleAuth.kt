package com.chmaba.pos.data.auth

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.chmaba.pos.data.plans.ApiClient

/**
 * Carries the OAuth result from [com.chmaba.pos.MainActivity]'s deep link into
 * the composition.
 *
 * The web app receives the token in its URL fragment; a phone cannot, so the
 * backend redirects to `chmaba://auth#access_token=…` instead and this object
 * hands the value to [AppRoot][com.chmaba.pos.ui.AppRoot].
 */
object DeepLink {
    var pendingToken by mutableStateOf<String?>(null)
    var pendingError by mutableStateOf<String?>(null)

    fun clear() {
        pendingToken = null
        pendingError = null
    }
}

const val AUTH_SCHEME = "chmaba"
const val AUTH_HOST = "auth"

/**
 * Opens the backend's Google authorize endpoint in a browser. `platform=android`
 * tells the callback to come back through [AUTH_SCHEME] rather than the web app.
 */
fun launchGoogleSignIn(context: Context, remember: Boolean = true) {
    val url = ApiClient.BASE_URL +
        "auth/google/authorize?remember=" + (if (remember) "1" else "0") + "&platform=android"
    context.startActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
    )
}

/** True when this intent is the OAuth redirect back into the app. */
fun isAuthDeepLink(uri: Uri?): Boolean =
    uri != null && uri.scheme == AUTH_SCHEME && uri.host == AUTH_HOST

/**
 * Reads the token (or the error) out of a `chmaba://auth#…` fragment. The backend
 * URL-encodes the fragment, so values are decoded here.
 */
fun parseAuthDeepLink(uri: Uri): Pair<String?, String?> {
    val fragment = uri.fragment ?: return null to null
    val params = fragment.split("&").mapNotNull { part ->
        val separator = part.indexOf('=')
        if (separator <= 0) null
        else part.substring(0, separator) to Uri.decode(part.substring(separator + 1))
    }.toMap()
    return (params["access_token"]?.takeIf { it.isNotBlank() }) to params["google_error"]
}
