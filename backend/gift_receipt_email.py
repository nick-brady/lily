"""The email a buyer gets after paying: the receipt page, in their inbox.

Stripe's own receipt says "Arrival Story $24.69" and nothing of the story;
ours shows the design, who it's going to, what it cost, the reference to
quote, and a link back to the receipt page. One email per order — the
webhook and the browser's confirm call both reach `send_for_orders`, and a
claim on `receipt_emailed_at` decides which of them sends.

Best effort throughout: the money has moved and the printer has the order
whether or not this lands. A failure is a warning in the log, never a failed
fulfillment.
"""
from __future__ import annotations

import html
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

import artwork_links
import messenger
import payments
from db import SessionLocal
from models import Birth, GiftOrder, User
from repositories import gift_orders as gift_orders_repo

logger = logging.getLogger(__name__)

# the design image in the email must outlive the inbox's habit of reopening
# things months later; a year is the S3 presign's practical ceiling anyway
IMAGE_TTL_SECONDS = 365 * 24 * 3600


def buyer_email_from(session_obj: dict | None, user: User | None) -> str | None:
    """Stripe's checkout collected an address; the account may have one too.
    Stripe's wins: it's the one the buyer typed a minute ago."""
    details = (session_obj or {}).get("customer_details") or {}
    for candidate in (details.get("email"), (session_obj or {}).get("customer_email"), getattr(user, "email", None)):
        if candidate and "@" in candidate:
            return candidate.strip()
    return None


def claim(db: Session, order_ids: list[uuid.UUID]) -> bool:
    """Mark these orders' receipt as sent, atomically, and say whether this
    caller was the one to do it. A losing caller sends nothing."""
    result = db.execute(
        update(GiftOrder)
        .where(GiftOrder.id.in_(order_ids), GiftOrder.receipt_emailed_at.is_(None))
        .values(receipt_emailed_at=datetime.now(timezone.utc))
    )
    db.commit()
    return (result.rowcount or 0) > 0


def unclaim(db: Session, order_ids: list[uuid.UUID]) -> None:
    """The send failed; let a later attempt try again."""
    db.execute(update(GiftOrder).where(GiftOrder.id.in_(order_ids)).values(receipt_emailed_at=None))
    db.commit()


def receipt_url(slug: str, order_id: uuid.UUID) -> str:
    return f"{payments.FRONTEND_URL}/b/{slug}/order/{order_id}"


def _money(cents: int) -> str:
    return f"${(cents or 0) / 100:,.2f}"


def build(lines: list[dict], *, birth: Birth, url: str) -> tuple[str, str, str]:
    """(subject, html, text). `lines` are receipt lines (see
    gift_orders.receipt_line) with `image_url` already made durable."""
    child = birth.child_name or "the baby"
    first = lines[0]
    subject = f"Your order is in — {first['item_display_name']} for {child}"

    def line_html(line: dict) -> str:
        item = html.escape(line["item_display_name"])
        option = f" &middot; {html.escape(line['product_display_name'])}" if line.get("product_display_name") else ""
        who = "to the family" if line["recipient_kind"] == "family" else "to you"
        where = f", in {html.escape(line['destination'])}" if line.get("destination") else ""
        image = (
            f'<img src="{html.escape(line["image_url"])}" alt="" width="96" height="96" '
            f'style="border-radius: 12px; object-fit: cover; display: block; margin: 0 0 12px;">'
            if line.get("image_url")
            else ""
        )
        message = (
            f'<p style="font-size: 14px; font-style: italic; color: #44364a; background: #faf7fc; '
            f'padding: 10px 14px; border-radius: 10px; margin: 12px 0 0;">'
            f'&ldquo;{html.escape(line["gift_message"])}&rdquo;<br>'
            f'<span style="font-style: normal; font-size: 12px; color: #6d6076;">printed on the packing slip</span></p>'
            if line.get("gift_message")
            else ""
        )
        return f"""\
  <div style="border-top: 1px solid #eee5f2; padding: 20px 0;">
    {image}
    <p style="font-size: 16px; margin: 0 0 4px;"><strong>{item}</strong>{option}</p>
    <p style="font-size: 14px; color: #6d6076; margin: 0 0 4px;">Going {who}{where}</p>
    <p style="font-size: 14px; color: #6d6076; margin: 0 0 12px;">Reference
      <span style="font-family: Menlo, Consolas, monospace; letter-spacing: 1px; color: #44364a;">{line['reference']}</span></p>
    <table style="font-size: 14px; border-collapse: collapse; width: 100%; max-width: 320px;">
      <tr><td style="padding: 2px 0; color: #6d6076;">{item}</td><td style="text-align: right;">{_money(line['product_price_cents'])}</td></tr>
      <tr><td style="padding: 2px 0; color: #6d6076;">Postage</td><td style="text-align: right;">{_money(line['shipping_cents'])}</td></tr>
      <tr><td style="padding: 6px 0 0; font-weight: bold;">Total</td><td style="text-align: right; padding-top: 6px; font-weight: bold;">{_money(line['amount_cents'])}</td></tr>
    </table>
    {message}
  </div>"""

    body_html = f"""\
<div style="font-family: Georgia, 'Times New Roman', serif; max-width: 460px;
            margin: 0 auto; padding: 32px 24px; color: #44364a;">
  <p style="font-size: 14px; letter-spacing: 2px; color: #a21caf;
            text-transform: uppercase; margin: 0 0 16px;">Arrival Story</p>
  <p style="font-size: 22px; margin: 0 0 8px;">Thank you &mdash; your order is in.</p>
  <p style="font-size: 14px; color: #6d6076; margin: 0 0 20px;">
    It's made to order and usually ships within a few business days.
  </p>
{''.join(line_html(l) for l in lines)}
  <a href="{html.escape(url)}"
     style="display: inline-block; background: #a21caf; color: #ffffff;
            text-decoration: none; padding: 12px 24px; border-radius: 8px;
            font-size: 16px; margin-top: 8px;">View your order</a>
  <p style="font-size: 13px; color: #6d6076; margin: 24px 0 0;">
    Questions? Reply to this email and quote the reference.
  </p>
</div>
"""

    def line_text(line: dict) -> str:
        who = "to the family" if line["recipient_kind"] == "family" else "to you"
        where = f", in {line['destination']}" if line.get("destination") else ""
        option = f" · {line['product_display_name']}" if line.get("product_display_name") else ""
        parts = [
            f"{line['item_display_name']}{option}",
            f"Going {who}{where}",
            f"Reference {line['reference']}",
            f"{line['item_display_name']}: {_money(line['product_price_cents'])}",
            f"Postage: {_money(line['shipping_cents'])}",
            f"Total: {_money(line['amount_cents'])}",
        ]
        if line.get("gift_message"):
            parts.append(f"Your message: “{line['gift_message']}”")
        return "\n".join(parts)

    text = (
        "Thank you — your order is in.\n"
        "It's made to order and usually ships within a few business days.\n\n"
        + "\n\n".join(line_text(l) for l in lines)
        + f"\n\nView your order: {url}\n\nQuestions? Reply to this email and quote the reference.\n"
    )
    return subject, body_html, text


def send_for_orders(order_ids: list[uuid.UUID], session_obj: dict | None) -> None:
    """Runs as a BackgroundTask after the response, with its own session.
    Records the buyer's email on the orders, claims the receipt, sends it."""
    db = SessionLocal()
    try:
        orders = list(db.scalars(select(GiftOrder).where(GiftOrder.id.in_(order_ids))))
        if not orders:
            return
        birth = db.get(Birth, orders[0].birth_id)
        user = db.get(User, orders[0].purchased_by_user_id) if orders[0].purchased_by_user_id else None
        to = buyer_email_from(session_obj, user)
        for o in orders:
            if not o.buyer_email and to:
                o.buyer_email = to
        db.commit()
        if not to:
            logger.warning("receipt not emailed: no address for order %s", orders[0].id)
            return
        if not claim(db, [o.id for o in orders]):
            return  # the other path got here first

        lines = [gift_orders_repo.receipt_line(db, o, birth) for o in orders]
        for o, line in zip(orders, lines):
            # the receipt page presigns S3 for an hour; an email needs longer
            line["image_url"] = (
                artwork_links.signed_artwork_url(o.gift_rendering_id, expires_in=IMAGE_TTL_SECONDS)
                if o.gift_rendering_id
                else None
            )
        subject, body_html, text = build(lines, birth=birth, url=receipt_url(birth.slug, orders[0].id))
        if not messenger.send_email(to=to, subject=subject, html=body_html, text=text):
            unclaim(db, [o.id for o in orders])
            logger.warning("receipt email failed for order %s; will not retry automatically", orders[0].id)
        else:
            logger.info("receipt emailed for order %s", orders[0].id)
    except Exception:  # noqa: BLE001 - see module docstring
        logger.warning("receipt email crashed for %s", order_ids, exc_info=True)
        db.rollback()
    finally:
        db.close()
