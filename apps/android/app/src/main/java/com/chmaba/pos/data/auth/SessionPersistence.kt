package com.chmaba.pos.data.auth

import android.content.Context
import android.content.SharedPreferences

/**
 * Persists the signed-in session so the app survives being killed or closed.
 *
 * Only the access token and a small profile are stored — never the password.
 * `Session` stays the in-memory holder; this is what restores it on launch.
 */
object SessionStore {

    private const val FILE = "chmaba_session"
    private const val KEY_TOKEN = "access_token"
    private const val KEY_NAME = "full_name"
    private const val KEY_EMAIL = "email"

    private var prefs: SharedPreferences? = null

    /** Called once from the Activity before the composition reads anything. */
    fun init(context: Context) {
        if (prefs == null) {
            prefs = context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        }
    }

    fun save(token: String, fullName: String?, email: String?) {
        prefs?.edit()
            ?.putString(KEY_TOKEN, token)
            ?.putString(KEY_NAME, fullName)
            ?.putString(KEY_EMAIL, email)
            ?.apply()
    }

    fun token(): String? = prefs?.getString(KEY_TOKEN, null)?.takeIf { it.isNotBlank() }

    fun fullName(): String? = prefs?.getString(KEY_NAME, null)

    fun email(): String? = prefs?.getString(KEY_EMAIL, null)

    fun clear() {
        prefs?.edit()?.clear()?.apply()
    }
}
