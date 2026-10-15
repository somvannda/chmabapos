package com.chmaba.pos.ui.screens.auth

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
import androidx.compose.foundation.clickable
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.foundation.background
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray700
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaViolet

@Composable
fun LoginScreen(
    onSignIn: (String, String) -> Unit,
    /** Google is asked to remember the session when the box beside the fields is ticked. */
    onGoogle: (Boolean) -> Unit,
    onForgotPassword: () -> Unit,
    onSignUp: () -> Unit,
    viewModel: LoginViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var rememberMe by remember { mutableStateOf(true) }

    // Only advance once the server has actually opened a session.
    LaunchedEffect(viewModel.signedIn) {
        if (viewModel.signedIn != null) onSignIn(email, password)
    }

    AuthScaffold(
        title = "A clearer way\nto run your day.",
        subtitle = "One home for every sale, every item, and every small win.",
    ) {
        Text(
            "Welcome back",
            color = ChmabaGray900,
            fontSize = 22.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
        Spacer(Modifier.height(4.dp))
        Text("Sign in to your workspace.", color = ChmabaGray500, fontSize = 12.5.sp)
        Spacer(Modifier.height(22.dp))

        ChmabaTextField(
            value = email,
            onValueChange = { email = it },
            label = "Email",
            placeholder = "you@store.com",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
        )
        PasswordField(
            value = password,
            onValueChange = { password = it },
            label = "Password",
        )

        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 2.dp, bottom = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(
                checked = rememberMe,
                onCheckedChange = { rememberMe = it },
                colors = CheckboxDefaults.colors(checkedColor = ChmabaBlue, uncheckedColor = ChmabaGray400),
                modifier = Modifier.size(22.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text("Remember me", color = ChmabaGray700, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.weight(1f))
            Text(
                text = "Forgot password?",
                color = ChmabaGray500,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.clickable(onClick = onForgotPassword),
            )
        }

        viewModel.error?.let { message ->
            Text(
                text = message,
                color = Color(0xFFC2564B),
                fontSize = 11.5.sp,
                lineHeight = 16.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 12.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color(0xFFFFF5F3))
                    .clickable { viewModel.dismissError() }
                    .padding(horizontal = 12.dp, vertical = 10.dp),
            )
        }

        ChmabaButton(
            onClick = { viewModel.signIn(email, password, rememberMe) },
            text = if (viewModel.busy) "Signing in…" else "Sign in",
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = email.isNotBlank() && password.isNotBlank() && !viewModel.busy,
        )

        OrDivider()
        GoogleButton(text = "Continue with Google", onClick = { onGoogle(rememberMe) })
        AuthSwap(lead = "New to Chmaba?", action = "Create an account", onAction = onSignUp)
        AuthNote("Protected by Cloudflare Turnstile")
    }
}

@Composable
fun SignupScreen(
    /** Called with the email once the server has accepted the registration. */
    onCreated: (String) -> Unit,
    onGoogle: () -> Unit,
    onSignIn: () -> Unit,
    viewModel: SignupViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var accepted by remember { mutableStateOf(false) }

    // The server has taken the details, so move on to the code.
    LaunchedEffect(viewModel.registered) {
        if (viewModel.registered) onCreated(email)
    }

    val mismatch = confirm.isNotEmpty() && confirm != password
    val canSubmit = name.isNotBlank() && email.isNotBlank() && password.isNotBlank() &&
        !mismatch && accepted

    AuthScaffold(
        title = "Create your workspace.",
        subtitle = "Free to start — no payment details needed.",
    ) {
        Text(
            "Tell us about you",
            color = ChmabaGray900,
            fontSize = 16.sp,
            fontWeight = FontWeight.ExtraBold,
        )
        Spacer(Modifier.height(4.dp))
        Text("You can invite your team later", color = ChmabaGray400, fontSize = 10.5.sp)
        Spacer(Modifier.height(20.dp))

        ChmabaTextField(
            value = name,
            onValueChange = { name = it },
            label = "Full name",
            placeholder = "e.g. your full name",
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
        )
        ChmabaTextField(
            value = email,
            onValueChange = { email = it },
            label = "Email",
            placeholder = "you@store.com",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
        )

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.weight(1f)) {
                PasswordField(password, { password = it }, label = "Password")
            }
            Box(Modifier.weight(1f)) {
                PasswordField(
                    value = confirm,
                    onValueChange = { confirm = it },
                    label = "Confirm",
                    hint = if (mismatch) "Passwords do not match" else null,
                )
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 2.dp, bottom = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(
                checked = accepted,
                onCheckedChange = { accepted = it },
                colors = CheckboxDefaults.colors(checkedColor = ChmabaBlue, uncheckedColor = ChmabaGray400),
                modifier = Modifier.size(22.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(
                "I agree to the Terms and Privacy Policy",
                color = ChmabaGray700,
                fontSize = 11.5.sp,
            )
        }

        viewModel.error?.let { message ->
            Text(
                message,
                color = Color(0xFFC2564B),
                fontSize = 11.5.sp,
                lineHeight = 16.sp,
                modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp),
            )
        }

        ChmabaButton(
            onClick = { viewModel.register(name, email, password) },
            text = if (viewModel.busy) "Creating…" else "Create account",
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = canSubmit,
        )

        OrDivider()
        GoogleButton(text = "Sign up with Google", onClick = onGoogle)
        AuthSwap(lead = "Already have an account?", action = "Sign in", onAction = onSignIn)
    }
}

@Composable
fun VerifyEmailScreen(
    email: String,
    onVerified: () -> Unit,
    onUseDifferentEmail: () -> Unit,
    viewModel: SignupViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    var code by remember { mutableStateOf("") }

    // The account is confirmed, which is what makes signing in work.
    LaunchedEffect(viewModel.verified) {
        if (viewModel.verified) onVerified()
    }

    AuthScaffold(
        title = "Confirm your email.",
        subtitle = "One quick step to secure your workspace.",
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            VerifyBadge()
            Spacer(Modifier.width(12.dp))
            Column {
                Text(
                    "Check your inbox",
                    color = ChmabaGray900,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text(
                    "We sent a 6-digit code to $email",
                    color = ChmabaGray400,
                    fontSize = 10.5.sp,
                    modifier = Modifier.padding(top = 2.dp),
                )
            }
        }

        Spacer(Modifier.height(22.dp))
        OtpField(value = code, onValueChange = { code = it })
        Spacer(Modifier.height(10.dp))

        Text(
            // There is no resend in this app - the code arrives by email - and the
            // countdown that used to sit here never counted anything.
            text = "Didn't get it? Check your inbox, then try again.",
            color = ChmabaGray400,
            fontSize = 10.5.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )

        viewModel.error?.let { message ->
            Text(
                message,
                color = Color(0xFFC2564B),
                fontSize = 11.5.sp,
                lineHeight = 16.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            )
        }

        ChmabaButton(
            onClick = { viewModel.verify(code) },
            text = if (viewModel.busy) "Confirming…" else "Confirm email & continue",
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = code.length == 6,
        )

        // The code is offered by Android above the keyboard (Autofill / Gmail).
        // We deliberately draw no control for it — only this explanation.
        Text(
            text = "Android offers the code above the keyboard. Chmaba never reads your inbox.",
            color = ChmabaGray400,
            fontSize = 10.sp,
            textAlign = TextAlign.Center,
            lineHeight = 15.sp,
            modifier = Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 4.dp),
        )

        ChmabaButton(
            onClick = onUseDifferentEmail,
            text = "Use a different email",
            modifier = Modifier.fillMaxWidth(),
            variant = ButtonVariant.Ghost,
            size = ButtonSize.Small,
        )
    }
}

@Composable
fun ResetPasswordScreen(
    email: String,
    onUpdate: (String) -> Unit,
    onBackToSignIn: () -> Unit,
) {
    var password by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    val mismatch = confirm.isNotEmpty() && confirm != password

    AuthScaffold(
        title = "A fresh key\nto your workspace.",
        subtitle = "Reset your password securely, then get back to running your store.",
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(42.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(ChmabaViolet.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = ChmabaIcons.Key,
                    contentDescription = null,
                    tint = ChmabaViolet,
                    modifier = Modifier.size(20.dp),
                )
            }
            Spacer(Modifier.width(12.dp))
            Column {
                Text(
                    "Set a new password",
                    color = ChmabaGray900,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text(
                    "For $email",
                    color = ChmabaGray400,
                    fontSize = 10.5.sp,
                    modifier = Modifier.padding(top = 2.dp),
                )
            }
        }

        Spacer(Modifier.height(22.dp))

        PasswordField(
            value = password,
            onValueChange = { password = it },
            label = "New password",
            hint = "At least 8 characters, with a number or symbol.",
        )
        PasswordField(
            value = confirm,
            onValueChange = { confirm = it },
            label = "Confirm password",
            hint = if (mismatch) "Passwords do not match" else null,
        )

        ChmabaButton(
            onClick = { onUpdate(password) },
            text = "Update password",
            modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
            variant = ButtonVariant.Primary,
            size = ButtonSize.Large,
            enabled = password.length >= 8 && !mismatch,
        )

        AuthSwap(lead = "Remembered it?", action = "Back to sign in", onAction = onBackToSignIn)
        AuthNote("You'll be signed out of other devices.")
    }
}
