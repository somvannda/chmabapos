package com.chmaba.pos.ui.screens.auth

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.auth.PasswordResetRepository
import kotlinx.coroutines.launch

/**
 * Asks the API to send a password-reset link.
 *
 * This app can only make the request: the link carries a token that only the web app can
 * consume, so nothing here sets a password.
 */
class PasswordResetViewModel(
    private val repository: PasswordResetRepository = PasswordResetRepository(),
) : ViewModel() {

    var busy by mutableStateOf(false)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    /** The API's own words once it has accepted the request. */
    var message by mutableStateOf<String?>(null)
        private set

    fun request(email: String) {
        if (busy || email.isBlank()) return
        busy = true
        error = null
        message = null
        viewModelScope.launch {
            repository.request(email)
                .onSuccess { message = it }
                .onFailure {
                    error = com.chmaba.pos.data.readableMessage(it) ?: "Could not send the link"
                }
            busy = false
        }
    }
}
