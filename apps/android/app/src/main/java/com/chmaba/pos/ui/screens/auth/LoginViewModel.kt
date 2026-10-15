package com.chmaba.pos.ui.screens.auth

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.auth.AuthRepository
import kotlinx.coroutines.launch

/** The store the session was opened against. */
data class SignedIn(val storeName: String)

/**
 * Signs in against the API and opens the session.
 *
 * Nothing is faked: a failure leaves the user on the form with the server's
 * message, rather than advancing into an unauthenticated workspace.
 */
class LoginViewModel(
    private val repository: AuthRepository = AuthRepository(),
) : ViewModel() {

    var busy by mutableStateOf(false)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    var signedIn by mutableStateOf<SignedIn?>(null)
        private set

    fun signIn(email: String, password: String) {
        if (busy) return
        busy = true
        error = null
        viewModelScope.launch {
            repository.signIn(email, password)
                .onSuccess { signedIn = SignedIn(it) }
                .onFailure { error = it.message ?: "Could not sign in" }
            busy = false
        }
    }

    fun dismissError() {
        error = null
    }

    /** Opens a session from a token the Google redirect handed back. */
    fun openSession(token: String) {
        if (busy) return
        busy = true
        error = null
        viewModelScope.launch {
            repository.openSession(token)
                .onSuccess { signedIn = SignedIn(it) }
                .onFailure { error = it.message ?: "Could not finish Google sign-in" }
            busy = false
        }
    }

    fun reportError(message: String) {
        error = message
    }

    /**
     * Clears the signed-in state. Without this the navigation effect in AppRoot
     * would see a still-valid session and bounce straight back into the workspace.
     */
    fun signOut() {
        signedIn = null
        error = null
        // The refresh cookies live in a process-wide jar, so they would outlive
        // this call. Drop them before the stored session goes.
        com.chmaba.pos.data.plans.ApiClient.cookieJar.clear()
        // Also drop the saved token, or the next launch would sign back in.
        com.chmaba.pos.data.auth.SessionStore.clear()
    }

    /**
     * Restores a saved session on launch so the app does not ask for credentials
     * again after being killed. Fails silently into the login form.
     */
    fun restoreSession() {
        if (busy || signedIn != null) return
        busy = true
        viewModelScope.launch {
            repository.restore()
                .onSuccess { signedIn = SignedIn(it) }
                .onFailure { /* no saved session, or it expired: show Login */ }
            busy = false
        }
    }
}
