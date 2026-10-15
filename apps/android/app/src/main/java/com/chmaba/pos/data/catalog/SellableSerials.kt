package com.chmaba.pos.data.catalog

/**
 * The units on this shelf that a sale may name.
 *
 * The API refuses a serial-tracked sale without its serial numbers (v1.py:5711), so this is
 * what the picker offers. A store may only sell its own units, or units that belong to no
 * store yet - a unit tagged to another shop is not this shop's to sell. The web POS applies
 * the same rule (apps/web/src/lib/posMath.js, `serialCandidatesFor`).
 *
 * Pure, so it is testable without a store, a server or an emulator - which matters here,
 * because a workspace with more than one store is the only way to reach the exclusion branch.
 */
fun sellableSerials(rows: List<ProductSerialDto>, storeId: String?): List<ProductSerialDto> =
    rows.filter { unit ->
        unit.status == "in_stock" && (unit.storeId == null || unit.storeId == storeId)
    }
