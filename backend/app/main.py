import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    accounts,
    analytics,
    auth,
    budgets,
    categories,
    imports,
    links,
    loans,
    market,
    contacts,
    debts,
    review,
    rules,
    settings_api,
    transactions,
    wishlist,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="حسابداری شخصی", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["contacts"])
app.include_router(rules.router, prefix="/api/rules", tags=["rules"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"])
app.include_router(debts.router, prefix="/api/debts", tags=["debts"])
app.include_router(links.router, prefix="/api/links", tags=["links"])
app.include_router(loans.router, prefix="/api/loans", tags=["loans"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(wishlist.router, prefix="/api/wishlist", tags=["wishlist"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])

# رسیدهای آپلودشده — پشت گیت ورود نیستند چون فقط روی لوکال‌هاست سرو می‌شوند
app.mount("/api/files/receipts", StaticFiles(directory=settings.receipts_dir), name="receipts")


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
