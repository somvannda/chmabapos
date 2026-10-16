package com.chmaba.pos.data.orders

import android.content.Context
import com.chmaba.pos.data.readableMessage
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.IOException
import kotlinx.coroutines.sync.Mutex

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
    /**
     * Why a replay was refused, or null while it has only ever failed on the network.
     *
     * A row the server has answered and refused will never send itself, and this is what lets the
     * till say so instead of retrying in silence. Absent from rows written before this existed,
     * which is why it defaults.
     */
    val lastError: String? = null,
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

    /** Records why a replay was refused, so the till can say so rather than retry in silence. */
    fun note(context: Context, clientOrderId: String, problem: String?) {
        val next = all(context).map {
            if (it.clientOrderId == clientOrderId) it.copy(lastError = problem) else it
        }
        prefs(context).edit().putString(KEY_ROWS, gson.toJson(next)).apply()
    }
}

/** Why the oldest unsent sale is still waiting, or null when none of them is stuck. */
fun queuedProblem(context: Context): String? =
    OfflineQueue.all(context).firstOrNull { it.lastError != null }?.lastError

/**
 * What to say about sales still waiting, or null when there is nothing to say.
 *
 * A waiting sale is not an error: it went to the queue because the network was down, and it will go
 * when the network returns. One the server has *refused* is the case this exists for - it will
 * never send itself, and until now nothing on the till said so, so a sale could sit in storage for
 * good while the cashier believed it had gone.
 */
fun queuedNotice(count: Int, problem: String?): String? = when {
    count <= 0 -> null
    problem != null ->
        (if (count == 1) "1 sale is kept and the server refused it: "
        else "$count sales are kept and the server refused one: ") + problem
    count == 1 -> "1 sale is waiting to be sent."
    else -> "$count sales are waiting to be sent."
}

/** Guards the flush, so two triggers - the app opening and the till opening - cannot run at once. */
private val flushLock = Mutex()

/**
 * Sends what an earlier failure left waiting, oldest first, and says how many went.
 *
 * Only a request that never reached the server is ever queued ([shouldQueue]), so a row is always a
 * sale the API has not seen. Replaying it is safe for the same reason a retry is: the request still
 * carries the `client_order_id` it was minted with, and the API dedupes on that. Rows belonging to
 * another store are left alone, so a cashier who has switched stores cannot post yesterday's sale
 * to today's books.
 *
 * A row that cannot be parsed is dropped: it can never be sent, and keeping it would only rot in
 * storage. Any other failure leaves the row in place to be tried again, because a sale is never
 * silently thrown away.
 *
 * This lives here rather than on a screen's view model because it is not a screen's job: it has to
 * run whether the app opened on the dashboard or on the till.
 */
suspend fun flushQueuedOrders(
    context: Context,
    orders: OrdersRepository = OrdersRepository(),
): Int {
    if (!flushLock.tryLock()) return 0
    try {
        var sent = 0
        for (row in OfflineQueue.all(context)) {
            if (!row.belongsTo(Session.storeId)) continue
            val held = runCatching {
                Gson().fromJson(row.bodyJson, OrderCreateDto::class.java)
            }.getOrNull()
            if (held == null) {
                OfflineQueue.remove(context, row.clientOrderId)
                continue
            }
            val attempt = runCatching { orders.createOrder(held) }
            if (attempt.isSuccess) {
                OfflineQueue.remove(context, row.clientOrderId)
                sent++
            } else {
                // The server answered and refused. The row stays - a sale is never thrown away -
                // but the reason is recorded, so the till can say why it is still there instead of
                // retrying it in silence for ever.
                OfflineQueue.note(
                    context,
                    row.clientOrderId,
                    attempt.exceptionOrNull()?.let { readableMessage(it) } ?: "The server refused it.",
                )
            }
        }
        return sent
    } finally {
        flushLock.unlock()
    }
}

/** What to tell the cashier when held sales finally went; null when there was nothing to send. */
fun heldSalesNotice(sent: Int): String? = when {
    sent <= 0 -> null
    sent == 1 -> "Sent the sale that could not go earlier."
    else -> "Sent $sent sales that could not go earlier."
}
