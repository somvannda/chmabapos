package com.chmaba.pos.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import com.chmaba.pos.data.auth.DeepLink
import com.chmaba.pos.data.auth.launchGoogleSignIn
import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.ui.screens.auth.LoginViewModel
import com.chmaba.pos.ui.screens.auth.LoginScreen
import com.chmaba.pos.ui.screens.auth.ResetPasswordScreen
import com.chmaba.pos.ui.screens.auth.SignupScreen
import com.chmaba.pos.ui.screens.auth.VerifyEmailScreen
import com.chmaba.pos.ui.screens.pos.POSScreen
import com.chmaba.pos.ui.screens.shell.MainShell
import com.chmaba.pos.ui.screens.splash.SplashScreen

/**
 * All destinations the app can show while the full navigation graph is built out.
 * Deliberately tiny: a single source of truth for "where am I", so the auth flow
 * can be ported and reviewed before wiring a real nav library.
 */
sealed interface AppScreen {
    data object Splash : AppScreen
    data object Login : AppScreen
    data object Signup : AppScreen
    data object Verify : AppScreen
    data object Reset : AppScreen
    data object Register : AppScreen
}

@Composable
fun AppRoot(modifier: Modifier = Modifier) {
    var screen by remember { mutableStateOf<AppScreen>(AppScreen.Splash) }
    /**
     * The address whose email has just been confirmed. Signing up leaves the account verified and
     * without a session - POST /auth/verify-email answers with the user and no token - so the last
     * step is still a sign-in, and this is what keeps that step from looking like a failure (#754).
     */
    var confirmedEmail by remember { mutableStateOf("") }
    var activeEmail by remember { mutableStateOf("") }
    val context = LocalContext.current
    val loginViewModel: LoginViewModel = viewModel()

    // The Google round-trip can return at any moment; open the session and go in.
    LaunchedEffect(DeepLink.pendingToken, DeepLink.pendingError) {
        val token = DeepLink.pendingToken
        val failure = DeepLink.pendingError
        if (token == null && failure == null) return@LaunchedEffect
        DeepLink.clear()
        screen = AppScreen.Login
        if (token != null) loginViewModel.openSession(token)
        if (failure != null) loginViewModel.reportError(failure)
    }

    LaunchedEffect(loginViewModel.signedIn) {
        if (loginViewModel.signedIn != null) screen = AppScreen.Register
    }

    // Reopen a saved session once, so a killed app does not ask for credentials.
    LaunchedEffect(Unit) {
        loginViewModel.restoreSession()
    }

    BackHandler(enabled = screen != AppScreen.Splash && screen != AppScreen.Login) {
        screen = when (screen) {
            AppScreen.Verify -> AppScreen.Signup
            AppScreen.Signup, AppScreen.Reset -> AppScreen.Login
            AppScreen.Register -> AppScreen.Login
            else -> AppScreen.Login
        }
    }

    Crossfade(
        targetState = screen,
        animationSpec = tween(durationMillis = 280),
        label = "app-root",
        modifier = modifier,
    ) { current ->
        when (current) {
            AppScreen.Splash -> SplashScreen(
                onFinished = { screen = AppScreen.Login },
            )

            AppScreen.Login -> LoginScreen(
                onSignIn = { _, _ -> screen = AppScreen.Register },
                onGoogle = { remember -> launchGoogleSignIn(context, remember) },
                onForgotPassword = { screen = AppScreen.Reset },
                onSignUp = { screen = AppScreen.Signup },
                prefilledEmail = confirmedEmail,
                viewModel = loginViewModel,
            )

            AppScreen.Signup -> SignupScreen(
                onCreated = { email ->
                    if (email.isNotBlank()) activeEmail = email
                    screen = AppScreen.Verify
                },
                onGoogle = { launchGoogleSignIn(context) },
                onSignIn = { screen = AppScreen.Login },
            )

            AppScreen.Verify -> VerifyEmailScreen(
                email = activeEmail,
                // The account exists and its code is confirmed, so sign-in now works.
                onVerified = {
                    confirmedEmail = activeEmail
                    screen = AppScreen.Login
                },
                onUseDifferentEmail = { screen = AppScreen.Signup },
            )

            AppScreen.Reset -> ResetPasswordScreen(
                email = activeEmail,
                onUpdate = { screen = AppScreen.Login },
                onBackToSignIn = { screen = AppScreen.Login },
            )

            AppScreen.Register -> MainShell(
                onSignOut = {
                    // Drop the token first so no in-flight request can use it, then
                    // clear the sign-in state so we are not bounced back in.
                    Session.clear()
                    loginViewModel.signOut()
                    screen = AppScreen.Login
                },
            )
        }
    }
}
