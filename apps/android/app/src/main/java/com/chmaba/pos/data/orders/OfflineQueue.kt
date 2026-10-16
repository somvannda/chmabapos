package com.chmaba.pos.data.orders

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.IOException

/**
 * Sales that could not be sent, kept until they can be.
 *
 * The till used to say "The cart is untouched - nothing was charged" and leave the cashier to retry
 * by hand. This holds the sale instead, keyed by the `client_order_id` the request already carries, so
 * a replay is a replay rather than a second sale.
 *
 * What may be queued is the whole safety of that, and it is a rule: a request that never reached the
 * server failed on the network and can be tried again; a request the server *answered* - a 400, a 403,
 * a 422 - was refused for a reason, and queuing it would retry a refusal forever. [shouldQueue] is that
 * distinction, and it is a pure function so a test can hold it.
 */
data class QueuedOrder(
    val storeId: String,
    val clientOrderId: String,
    /** The request as it was to be sent, so a replay is the same sale with the same key. */
    val bodyJson: String,
    val queuedAt: Long,
)

/** True when a failure is worth retrying later: the server never answered. */
fun shouldQueue(problem: Throwable): Boolean = problem is IOException

/**
 * True when a row belongs to the store now signed in.
 *
 * The queue outlives a store switch, and a sale rung at one counter must not be posted to another
 * store's books. A row whose store was not recorded travels with whoever is signed in, which is the
 * best that can be said for it.
 */
fun QueuedOrder.belongsTo(storeId: String?): Boolean =
    this.storeId.isBlank() || storeId.isNullOrBlank() || this.storeId == storeId

private const val FILE = "chmaba_offline_queue"
private const val KEY_ROWS = "orders"

object OfflineQueue {
    private val gson = Gson()

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /** Everything still waiting, oldest first. */
    fun all(context: Context): List<QueuedOrder> {
        val raw = prefs(context).getString(KEY_ROWS, null) ?: return emptyList()
        return try {
            val type = object : TypeToken<List<QueuedOrder>>() {}.type
            gson.fromJson<List<QueuedOrder>>(raw, type) ?: emptyList()
        } catch (problem: Exception) {
            // A queue that cannot be read must not take the till down with it.
            emptyList()
        }
    }

    fun add(context: Context, row: QueuedOrder) {
        // One row per sale: the key is what makes a replay safe, so it is what identifies the row.
        val next = all(context).filterNot { it.clientOrderId == row.clientOrderId } + row
        prefs(context).edit().putString(KEY_ROWS, gson.toJson(next)).apply()
    }

    fun remove(context: Context, clientOrderId: String) {
        val next = all(context).filterNot { it.clientOrderId == clientOrderId }
        prefs(context).edit().putString(KEY_ROWS, gson.toJson(next)).apply()
    }

    fun size(context: Context): Int = all(context).size
}
