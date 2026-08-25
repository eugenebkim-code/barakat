import json
import os
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def load_google_credentials():
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    file_path = os.getenv("GOOGLE_CREDENTIALS_FILE", "").strip()

    candidates = []
    if raw:
        candidates.append(raw)
    if file_path:
        candidates.append(file_path)

    for candidate in candidates:
        try:
            if candidate.startswith("{"):
                return json.loads(candidate)
            if candidate and os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as fh:
                    return json.load(fh)
        except (OSError, ValueError, json.JSONDecodeError):
            continue

    raise RuntimeError(
        "Google Sheets credentials missing or invalid. Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_FILE to a valid service-account JSON."
    )


SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise RuntimeError("Google Sheets ENV vars missing")

GOOGLE_CREDS_INFO = load_google_credentials()

SHOP_NAME = "БАРАКАТ"
SHOP_PHONE = "010-8207-4445"
SHOP_NOTE = "Традиционная узбекская кухня. ХАЛАЛ"
FREE_DELIVERY_FROM = 30000
DELIVERY_FEE = 4000


def get_sheets_service():
    creds = Credentials.from_service_account_info(
        GOOGLE_CREDS_INFO,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def read_products_from_sheets() -> list[dict]:
    service = get_sheets_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="products!A2:G",
    ).execute()

    rows = result.get("values", [])
    products: list[dict] = []

    for row in rows:
        if len(row) < 5:
            continue
        products.append(
            {
                "product_id": row[0],
                "name": row[1],
                "price": int(row[2]),
                "available": row[3].lower() == "true",
                "category": row[4],
                "photo_file_id": row[5] if len(row) > 5 else None,
                "description": row[6] if len(row) > 6 else None,
            }
        )

    return products


def get_product_by_id(pid: str) -> dict | None:
    for p in read_products_from_sheets():
        if p["product_id"] == pid:
            return p
    return None


def _fmt_money(krw: int) -> str:
    return f"{krw:,}₩"


def cart_total(cart: dict) -> int:
    total = 0
    for pid, qty in cart.items():
        p = get_product_by_id(pid)
        if p:
            total += p["price"] * qty
    return total


def calc_delivery_fee(cart: dict, kind: str) -> int:
    if kind != "delivery":
        return 0

    subtotal = cart_total(cart)
    if subtotal >= FREE_DELIVERY_FROM:
        return 0
    return DELIVERY_FEE


def cart_text(cart: dict) -> str:
    if not cart:
        return "Корзина пустая."

    lines = []
    for pid, qty in cart.items():
        p = get_product_by_id(pid)
        if not p:
            continue
        lines.append(f"• {p['name']} × {qty} = {_fmt_money(p['price'] * qty)}")

    lines.append("")
    lines.append(f"Итого: {_fmt_money(cart_total(cart))}")
    return "\n".join(lines)


def save_order_to_sheets(
    user,
    cart: dict,
    kind: str,
    comment: str,
    address: str | None = None,
) -> str | None:
    service = get_sheets_service()
    sheet = service.spreadsheets()

    items = []
    subtotal = 0
    for pid, qty in cart.items():
        p = get_product_by_id(pid)
        if not p:
            continue
        items.append(f"{p['name']} x{qty}")
        subtotal += p["price"] * qty

    delivery_fee = 0
    if kind == "Доставка" or kind == "delivery":
        if subtotal < FREE_DELIVERY_FROM:
            delivery_fee = DELIVERY_FEE

    total = subtotal + delivery_fee
    order_id = str(uuid4())
    created_at = datetime.utcnow().isoformat()

    row = [[
        order_id,
        created_at,
        str(getattr(user, 'id', 'webapp')),
        getattr(user, 'username', '') or '',
        '; '.join(items),
        total,
        kind,
        comment or '',
        '',
        'waiting_payment',
        '',
        '',
        '',
        address or '',
        delivery_fee,
    ]]

    try:
        resp = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="orders!A:O",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()
        return order_id
    except Exception:
        return None


def update_order_payment(order_id: str, payment_file_id: str | None, status: str = "pending"):
    if not order_id:
        return False
    service = get_sheets_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="orders!A:O",
    ).execute()
    rows = result.get("values", [])

    target_row = None
    for idx, row in enumerate(rows, start=1):
        if row and row[0] == order_id:
            target_row = idx
            break

    if target_row is None:
        return False

    data = []
    if payment_file_id:
        data.append({"range": f"orders!I{target_row}", "values": [[payment_file_id]]})
    data.append({"range": f"orders!J{target_row}", "values": [[status]]})

    sheet.values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()
    return True


def build_checkout_preview(cart: dict, kind_label: str, comment: str, address: str | None = None) -> str:
    kind = "delivery" if kind_label == "Доставка" else "pickup"
    subtotal = cart_total(cart)
    delivery_fee = calc_delivery_fee(cart, kind)
    total = subtotal + delivery_fee

    address_block = f"Адрес: <b>{address}</b>\n" if address else ""
    delivery_block = ""
    if kind == "delivery":
        if delivery_fee == 0:
            delivery_block = "🚚 Доставка: <b>бесплатно</b>\n"
        else:
            delivery_block = f"🚚 Доставка: <b>{_fmt_money(delivery_fee)}</b>\n"

    return (
        "🧾 <b>Проверьте заказ</b>\n\n"
        f"{cart_text(cart)}\n\n"
        f"{delivery_block}"
        f"💰 <b>Итого к оплате: {_fmt_money(total)}</b>\n\n"
        f"Способ: <b>{kind_label}</b>\n"
        f"{address_block}"
        f"Комментарий: <b>{comment or '—'}</b>\n\n"
        "На этом этапе необходимо произвести оплату на наш тонжан и прикрепить скриншот ⬇️"
    )


def get_categories_from_products(products: list[dict]) -> list[str]:
    return sorted({p["category"] for p in products if p.get("category") and p.get("available")})


def product_payload(product: dict) -> dict:
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "price": product["price"],
        "available": product["available"],
        "category": product["category"],
        "description": product.get("description") or "",
        "photo_file_id": product.get("photo_file_id") or "",
    }
