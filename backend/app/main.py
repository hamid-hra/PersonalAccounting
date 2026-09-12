import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
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
    files,
    review,
    rules,
    settings_api,
    transactions,
    wishlist,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)

# مستندات API فقط وقتی صریحاً خواسته شود (EXPOSE_API_DOCS=1) منتشر می‌شود
app = FastAPI(
    title="حسابداری شخصی",
    docs_url="/api/docs" if settings.expose_api_docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.expose_api_docs else None,
)

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

# رسیدهای آپلودشده — پشت گیت ورود
app.include_router(files.router, prefix="/api/files", tags=["files"])


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------- سرآیندهای امنیتی
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---------------------------------------------------------------- فرانت
# خروجی ساخته‌شدهٔ React کنار بک‌اند سرو می‌شود: یک کانتینر، یک پورت، بدون
# nginx و بدون نیاز به شبکهٔ بین‌سرویسی. هر مسیر غیر-API به index.html می‌رود.
_static = settings.static_dir
if _static is not None:
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (_static / path).resolve()
        if path and candidate.is_file() and _static.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html", headers={"Cache-Control": "no-cache"})
