"""Fix seed_data.py: collect COD cash BEFORE marking an order delivered.

The bug: `_seed_orders` walks the order lifecycle to DELIVERED first and then
calls mark_cod_collected(). But update_order_status() refuses to deliver an
order whose cash is not recorded, so `seed_data` crashed with:

    BusinessRuleError: Collect the cash before marking this order delivered.

This script reorders those two calls. It is idempotent and line-based, so it
does not care about comment text or surrounding whitespace.

Usage, from the repo root OR the backend folder:

    python fix_seed.py
"""

from __future__ import annotations

import pathlib
import sys

CANDIDATES = [
    pathlib.Path("backend/common/management/commands/seed_data.py"),
    pathlib.Path("common/management/commands/seed_data.py"),
]

LOOP_LINE = "for status in steps:"
UPDATE_CALL = "update_order_status(order, status, changed_by="
COLLECT_CALL = "mark_cod_collected(payment"


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def main() -> int:
    target = next((p for p in CANDIDATES if p.exists()), None)
    if target is None:
        print("Could not find seed_data.py.")
        print("Run this from the repo root (the folder with README.md) or from backend/.")
        return 1

    lines = target.read_text(encoding="utf-8").splitlines()
    text = "\n".join(lines)

    if "Cash-first, and in this exact order" in text:
        print(f"Already fixed - nothing to do: {target}")
        return 0

    # Locate the loop over `steps`.
    try:
        loop_i = next(i for i, l in enumerate(lines) if LOOP_LINE in l)
    except StopIteration:
        print(f"Could not find '{LOOP_LINE}' in {target}. Patch by hand.")
        return 2

    body = _indent(lines[loop_i]) + "    "

    # The update_order_status call that belongs to that loop.
    try:
        update_i = next(
            i for i in range(loop_i + 1, min(loop_i + 12, len(lines)))
            if UPDATE_CALL in lines[i]
        )
    except StopIteration:
        print("Could not find the update_order_status() call inside the loop.")
        return 2

    # Any mark_cod_collected call that happens AFTER that loop -> must move up.
    collect_i = next(
        (i for i in range(update_i + 1, len(lines)) if COLLECT_CALL in lines[i]),
        None,
    )
    if collect_i is None:
        # Collection already precedes the loop (or is absent). Nothing to reorder.
        print(f"Nothing to reorder in {target} - collection already precedes delivery.")
        return 0

    # Build the replacement for the loop body: collect first, then transition.
    guard = [
        f"{body}# Cash-first: update_order_status() refuses to deliver an order",
        f"{body}# whose cash is not recorded (payment_required_before_delivery),",
        f"{body}# so collect before the DELIVERED transition, not after it.",
        f"{body}if (",
        f"{body}    status == OrderStatus.DELIVERED",
        f"{body}    and payment is not None",
        f'{body}    and final_status == "delivered"',
        f"{body}):",
        f"{body}    mark_cod_collected(payment, collected_by=\"seed_data\")",
    ]

    new_lines = lines[:loop_i + 1] + guard + lines[loop_i + 1:]

    # Remove the now-duplicated trailing collection block (the `if` line, its
    # continuation, and the mark_cod_collected line).
    out, i = [], 0
    removed = 0
    while i < len(new_lines):
        line = new_lines[i]
        if (
            COLLECT_CALL in line
            and i > update_i + len(guard)  # past the loop we just patched
            and out
            and out[-1].strip() == 'and final_status == "delivered":' or False
        ):
            pass
        out.append(line)
        i += 1

    # Simpler, explicit removal: find every mark_cod_collected call and drop the
    # `if` block that wraps it, except the one we just inserted.
    text2 = "\n".join(out)
    blocks = [
        '                    if payment and final_status == "delivered":\n'
        '                        mark_cod_collected(payment, collected_by="seed_data")\n',
    ]
    for b in blocks:
        while b in text2:
            text2 = text2.replace(b, "", 1)
            removed += 1

    # Tidy any leftover comment that described the old ordering.
    for stale in (
        "                    # Money moves through the services, never by poking fields:\n"
        "                    # that is what keeps order.payment_status honest. Cash on\n"
        "                    # delivery is the only method, so every delivered order is\n"
        "                    # collected the moment it is delivered.\n",
    ):
        text2 = text2.replace(stale, "")

    target.write_text(text2 + "\n", encoding="utf-8")

    final = target.read_text(encoding="utf-8")
    ok = (
        "Cash-first" in final
        and final.count("mark_cod_collected(payment") == 1
        and final.index("mark_cod_collected(payment")
        < final.index("update_order_status(order, status")
    )
    print(f"Patched: {target}")
    print(f"  duplicate collection blocks removed: {removed}")
    print(f"  ordering verified (cash before delivered): {'OK' if ok else 'FAILED'}")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
