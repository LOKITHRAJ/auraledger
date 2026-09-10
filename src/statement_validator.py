import logging
from typing import Any, Dict, List

logger = logging.getLogger("AuraLedger")


def validate_balance_continuity(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Checks whether a statement's debits/credits reconcile against its printed
    closing balance. Informational only -- never blocks import, since bank
    charges, rounding, or a partial statement period can legitimately cause a
    mismatch (per product decision: report the discrepancy, don't reject on it).
    """
    if not transactions:
        return {
            "transaction_count": 0,
            "opening_balance": None,
            "closing_balance": None,
            "calculated_balance": None,
            "validation_status": "no_transactions",
        }

    total_debit = sum(float(t.get("debit") or 0) for t in transactions)
    total_credit = sum(float(t.get("credit") or 0) for t in transactions)
    closing_balance = float(transactions[-1].get("balance") or 0)

    # Infer the opening balance by working backwards from the first transaction's
    # own printed balance -- no separate "opening balance" field exists on the
    # normalized transaction model.
    first = transactions[0]
    first_balance = float(first.get("balance") or 0)
    first_debit = float(first.get("debit") or 0)
    first_credit = float(first.get("credit") or 0)
    opening_balance = first_balance + first_debit - first_credit

    calculated_balance = opening_balance + total_credit - total_debit
    status = "matched" if abs(calculated_balance - closing_balance) < 0.01 else "mismatch"

    return {
        "transaction_count": len(transactions),
        "opening_balance": round(opening_balance, 2),
        "closing_balance": round(closing_balance, 2),
        "calculated_balance": round(calculated_balance, 2),
        "validation_status": status,
    }


def flag_duplicate_transactions(transactions: List[Dict[str, Any]]) -> int:
    """
    Flags (does not remove) transactions that exactly match an earlier one in
    the same list on date + debit + credit + narration + reference. Mutates each
    transaction dict in place, adding `is_duplicate`. Returns how many were flagged.
    """
    seen = set()
    duplicate_count = 0

    for txn in transactions:
        key = (
            txn.get("date"),
            round(float(txn.get("debit") or 0), 2),
            round(float(txn.get("credit") or 0), 2),
            (txn.get("narration") or "").strip().lower(),
            (txn.get("reference") or "").strip(),
        )
        if key in seen:
            txn["is_duplicate"] = True
            duplicate_count += 1
        else:
            txn["is_duplicate"] = False
            seen.add(key)

    if duplicate_count:
        logger.info(f"Flagged {duplicate_count} duplicate-looking transaction(s) for review.")

    return duplicate_count
