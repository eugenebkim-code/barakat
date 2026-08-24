import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from shop_service import (
    build_checkout_preview,
    calc_delivery_fee,
    cart_total,
    get_categories_from_products,
    product_payload,
    read_products_from_sheets,
    save_order_to_sheets,
    update_order_payment,
)

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "miniapp" / "dist"

app = FastAPI(title="BARAKAT mini app")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "BARAKAT mini app"}


@app.get("/api/products")
def list_products():
    products = read_products_from_sheets()
    return {
        "products": [product_payload(p) for p in products if p["available"]],
        "categories": get_categories_from_products(products),
    }


@app.post("/api/orders")
def create_order(payload: dict):
    cart = payload.get("cart") or {}
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    buyer = SimpleNamespace(
        id=payload.get("user_id") or 0,
        username=payload.get("username") or "miniapp",
    )

    kind = payload.get("kind") or "pickup"
    kind_label = "Доставка" if kind == "delivery" else "Самовывоз"

    order_id = save_order_to_sheets(
        user=buyer,
        cart=cart,
        kind=kind_label,
        comment=payload.get("comment") or "",
        address=payload.get("address"),
    )

    if not order_id:
        raise HTTPException(status_code=500, detail="Could not create order")

    if payload.get("payment_proof"):
        update_order_payment(order_id, payload.get("payment_proof"), "pending")

    subtotal = cart_total(cart)
    delivery_fee = calc_delivery_fee(cart, kind)
    total = subtotal + delivery_fee

    return {
        "ok": True,
        "order_id": order_id,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
        "preview": build_checkout_preview(
            cart=cart,
            kind_label=kind_label,
            comment=payload.get("comment") or "",
            address=payload.get("address"),
        ),
    }


if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
else:
    @app.get("/")
    def index_redirect():
        return {"message": "Run npm install && npm run build in miniapp first"}
