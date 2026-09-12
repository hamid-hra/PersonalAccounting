"""
منطق مشترک بازار: ذخیرهٔ قیمت، آمار توصیفی، سبد دارایی و نگهبان سهمیه.

این لایه از سرویسِ قیمت مستقل است — عوض‌کردن provider هیچ‌جای دیگری را
تغییر نمی‌دهد.
"""

import statistics
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ApiCallLog, AssetHolding, MarketItem, PriceAlert, PricePoint
from app.services import appsettings
from app.services.jalali import to_jalali_str
from app.services.market.base import (
    MarketProvider,
    MarketUnavailable,
    QuotaExhausted,
)
from app.services.market.brsapi import BrsApiProvider
from app.services.market.navasan import NavasanProvider

_PROVIDER_CLASSES: dict[str, type[MarketProvider]] = {
    BrsApiProvider.name: BrsApiProvider,
    NavasanProvider.name: NavasanProvider,
}


def provider(db: Session) -> MarketProvider:
    """
    سرویس فعال، با کلیدی که کاربر در تنظیمات ثبت کرده.

    هر بار نمونهٔ تازه ساخته می‌شود تا کلیدِ یک درخواست به درخواست دیگر
    نشت نکند و تغییر تنظیمات بلافاصله اثر بگذارد.
    """
    name = appsettings.get(db, appsettings.MARKET_PROVIDER, "brsapi") or "brsapi"
    cls = _PROVIDER_CLASSES.get(name, BrsApiProvider)
    return cls(api_key=appsettings.get(db, cls.key_setting, "") or "")


def all_providers() -> list[dict]:
    return [
        {"name": cls.name, "label_fa": cls.label_fa, "key_setting": cls.key_setting}
        for cls in _PROVIDER_CLASSES.values()
    ]


# ---------------------------------------------------------------- سهمیه
def _window_start(window: str) -> datetime:
    now = datetime.utcnow()
    if window == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def quota_status(db: Session) -> dict:
    prov = provider(db)
    spec = prov.quota()
    used = (
        db.scalar(
            select(func.count())
            .select_from(ApiCallLog)
            .where(
                ApiCallLog.provider == prov.name,
                ApiCallLog.called_at >= _window_start(spec.window),
            )
        )
        or 0
    )
    return {
        "provider": prov.name,
        "provider_label": prov.label_fa,
        "window": spec.window,
        "window_label": spec.label_fa,
        "used": used,
        "limit": spec.limit,
        "reserve": spec.reserve,
        "remaining": max(spec.limit - used, 0),
        "usable": max(spec.limit - spec.reserve - used, 0),
        "configured": prov.is_configured(),
    }


def _guard(db: Session) -> MarketProvider:
    status = quota_status(db)
    prov = provider(db)
    if not status["configured"]:
        raise MarketUnavailable(
            f"کلید سرویس {prov.label_fa} تنظیم نشده است."
        )
    if status["usable"] <= 0:
        raise QuotaExhausted(
            f"سهمیهٔ {status['window_label']} تمام شده "
            f"({status['used']} از {status['limit']}). قیمت‌های ذخیره‌شده همچنان کار می‌کنند."
        )
    return prov


def _log(db: Session, endpoint: str) -> ApiCallLog:
    entry = ApiCallLog(provider=provider(db).name, endpoint=endpoint)
    db.add(entry)
    db.commit()
    return entry


# ---------------------------------------------------------------- اقلام
def seed_items(db: Session) -> int:
    """
    اقلام سرویس فعال را می‌سازد و اقلام سرویس‌های دیگر را کنار می‌گذارد،
    تا فهرست بازار همیشه با چیزی که واقعاً می‌شود گرفت بخواند.
    """
    prov = provider(db)
    wanted = {i.code: i for i in prov.items}
    existing = {i.code: i for i in db.scalars(select(MarketItem))}

    added = 0
    for code, item in wanted.items():
        row = existing.get(code)
        if row is None:
            db.add(
                MarketItem(
                    code=code,
                    label_fa=item.label_fa,
                    kind=item.kind,
                    unit_fa=item.unit_fa,
                    sort_order=item.sort_order,
                    is_tracked=True,
                )
            )
            added += 1
        else:
            row.is_tracked = True
            row.label_fa = item.label_fa
            row.sort_order = item.sort_order

    for code, row in existing.items():
        if code not in wanted:
            row.is_tracked = False
    db.commit()
    return added


def tracked_codes(db: Session) -> list[str]:
    return [
        i.code
        for i in db.scalars(
            select(MarketItem).where(MarketItem.is_tracked).order_by(MarketItem.sort_order)
        )
    ]


# ---------------------------------------------------------------- ذخیره
def _store(db: Session, code: str, day: date, close: int, **extra) -> bool:
    row = db.scalar(
        select(PricePoint).where(PricePoint.item_code == code, PricePoint.price_date == day)
    )
    if row is None:
        row = PricePoint(
            item_code=code, price_date=day, jalali_date=to_jalali_str(day), close_rial=close
        )
        db.add(row)
        created = True
    else:
        row.close_rial = close
        created = False
    for key, value in extra.items():
        if value is not None:
            setattr(row, key, value)
    row.source = provider(db).name
    return created


def refresh_prices(db: Session) -> dict:
    """قیمت امروزِ همهٔ اقلام با **یک** درخواست."""
    seed_items(db)
    prov = _guard(db)
    entry = _log(db, "latest")
    try:
        quotes = prov.fetch_latest(tracked_codes(db))
    except Exception as exc:
        entry.ok = False
        entry.detail = str(exc)[:280]
        db.commit()
        raise

    created = 0
    for q in quotes:
        if _store(
            db,
            q.code,
            q.as_of or date.today(),
            q.price_rial,
            change_percent=q.change_percent,
        ):
            created += 1
    db.commit()
    check_alerts(db)
    return {"items": len(quotes), "new_points": created, "date": to_jalali_str(date.today())}


def backfill_history(db: Session, code: str, days: int = 365) -> dict:
    """تاریخچهٔ یک قلم — یک درخواست برای کل بازه، یک‌بار برای همیشه."""
    seed_items(db)
    prov = _guard(db)
    end = date.today()
    start = end - timedelta(days=days)
    entry = _log(db, "history")
    try:
        points = prov.fetch_history(code, start, end)
    except Exception as exc:
        entry.ok = False
        entry.detail = str(exc)[:280]
        db.commit()
        raise

    created = 0
    for p in points:
        if _store(
            db,
            code,
            p.day,
            p.close_rial,
            open_rial=p.open_rial,
            high_rial=p.high_rial,
            low_rial=p.low_rial,
        ):
            created += 1
    db.commit()
    return {"item": code, "new_points": created, "fetched": len(points), "range_days": days}


# ---------------------------------------------------------------- خواندن
def latest_price(db: Session, code: str) -> PricePoint | None:
    return db.scalar(
        select(PricePoint)
        .where(PricePoint.item_code == code)
        .order_by(PricePoint.price_date.desc())
        .limit(1)
    )


def price_series(db: Session, code: str, days: int = 365) -> list[PricePoint]:
    since = date.today() - timedelta(days=days)
    return list(
        db.scalars(
            select(PricePoint)
            .where(PricePoint.item_code == code, PricePoint.price_date >= since)
            .order_by(PricePoint.price_date)
        )
    )


def item_stats(db: Session, code: str) -> dict:
    """
    آمار توصیفی — نه پیش‌بینی.

    هیچ سیگنال خرید/فروش تولید نمی‌شود؛ فقط آنچه در داده هست.
    """
    series = price_series(db, code, days=400)
    if not series:
        return {"code": code, "has_data": False}

    closes = [p.close_rial for p in series]
    latest = series[-1]

    def change_over(days: int) -> float | None:
        cutoff = latest.price_date - timedelta(days=days)
        past = [p for p in series if p.price_date <= cutoff]
        if not past:
            return None
        base = past[-1].close_rial
        return (latest.close_rial - base) / base if base else None

    def ma(window: int) -> int | None:
        return int(statistics.mean(closes[-window:])) if len(closes) >= window else None

    peak = max(series, key=lambda p: p.close_rial)
    trough = min(series, key=lambda p: p.close_rial)
    returns = [(b - a) / a for a, b in zip(closes, closes[1:]) if a]
    volatility = statistics.pstdev(returns) * (365 ** 0.5) if len(returns) > 2 else None

    return {
        "code": code,
        "has_data": True,
        "latest_rial": latest.close_rial,
        "latest_date": latest.jalali_date,
        "change_percent": latest.change_percent,
        "points": len(series),
        "change_7d": change_over(7),
        "change_30d": change_over(30),
        "change_90d": change_over(90),
        "change_365d": change_over(365),
        "ma_7": ma(7),
        "ma_30": ma(30),
        "ma_90": ma(90),
        "high_rial": peak.close_rial,
        "high_date": peak.jalali_date,
        "low_rial": trough.close_rial,
        "low_date": trough.jalali_date,
        "from_high": (latest.close_rial - peak.close_rial) / peak.close_rial
        if peak.close_rial
        else None,
        "volatility_annual": volatility,
    }


def observations(db: Session) -> list[dict]:
    """
    مشاهده‌های **واقعی** دربارهٔ قیمت‌ها — نه توصیه.

    هرکدام یک جملهٔ قابل‌راستی‌آزمایی است: «امروز چقدر تغییر کرد»،
    «نسبت به میانگین کجاست»، «آیا به سقف/کف دوره رسیده». هیچ‌کدام
    نمی‌گویند بخر یا بفروش.
    """
    out = []
    items = {i.code: i for i in db.scalars(select(MarketItem).where(MarketItem.is_tracked))}
    for code, item in items.items():
        stats = item_stats(db, code)
        if not stats.get("has_data"):
            continue
        latest = stats["latest_rial"]

        if stats.get("change_percent"):
            pct = stats["change_percent"]
            out.append(
                {
                    "item_code": code,
                    "item_label": item.label_fa,
                    "tone": "gain" if pct >= 0 else "loss",
                    "text": f"{item.label_fa} امروز {abs(pct):.2f}٪ "
                    + ("بالا رفت" if pct >= 0 else "پایین آمد"),
                }
            )

        series_90 = price_series(db, code, 90)
        if len(series_90) >= 10:
            highs = max(p.close_rial for p in series_90)
            lows = min(p.close_rial for p in series_90)
            if latest >= highs:
                out.append(
                    {
                        "item_code": code,
                        "item_label": item.label_fa,
                        "tone": "gain",
                        "text": f"{item.label_fa} در بالاترین قیمت ۹۰ روز اخیر است",
                    }
                )
            elif latest <= lows:
                out.append(
                    {
                        "item_code": code,
                        "item_label": item.label_fa,
                        "tone": "loss",
                        "text": f"{item.label_fa} در پایین‌ترین قیمت ۹۰ روز اخیر است",
                    }
                )

        ma30 = stats.get("ma_30")
        if ma30 and abs(latest - ma30) / ma30 >= 0.05:
            diff = (latest - ma30) / ma30
            out.append(
                {
                    "item_code": code,
                    "item_label": item.label_fa,
                    "tone": "neutral",
                    "text": f"{item.label_fa} {abs(diff) * 100:.0f}٪ "
                    + ("بالاتر" if diff > 0 else "پایین‌تر")
                    + " از میانگین ۳۰ روزه است",
                }
            )
    return out


# ---------------------------------------------------------------- هشدار
def check_alerts(db: Session) -> list[PriceAlert]:
    """هشدارهایی که سقف/کفشان رد شده — خودِ کاربر آستانه را گذاشته."""
    triggered = []
    for alert in db.scalars(select(PriceAlert).where(PriceAlert.is_active)):
        price = latest_price(db, alert.item_code)
        if price is None:
            continue
        hit = (
            price.close_rial >= alert.threshold_rial
            if alert.direction == "above"
            else price.close_rial <= alert.threshold_rial
        )
        if hit:
            alert.last_triggered_at = datetime.utcnow()
            alert.last_price_rial = price.close_rial
            triggered.append(alert)
    db.commit()
    return triggered


def active_alerts(db: Session) -> list[dict]:
    items = {i.code: i for i in db.scalars(select(MarketItem))}
    out = []
    for alert in db.scalars(select(PriceAlert).order_by(PriceAlert.id.desc())):
        price = latest_price(db, alert.item_code)
        item = items.get(alert.item_code)
        current = price.close_rial if price else None
        hit = current is not None and (
            current >= alert.threshold_rial
            if alert.direction == "above"
            else current <= alert.threshold_rial
        )
        out.append(
            {
                "id": alert.id,
                "item_code": alert.item_code,
                "item_label": item.label_fa if item else alert.item_code,
                "direction": alert.direction,
                "direction_label": "بالاتر از" if alert.direction == "above" else "پایین‌تر از",
                "threshold_rial": alert.threshold_rial,
                "current_rial": current,
                "is_active": alert.is_active,
                "is_triggered": bool(hit),
                "note": alert.note,
            }
        )
    return out


# ---------------------------------------------------------------- سبد
def portfolio(db: Session) -> dict:
    holdings = list(db.scalars(select(AssetHolding)))
    items = {i.code: i for i in db.scalars(select(MarketItem))}
    rows = []
    total_value = total_cost = today_change = 0

    for h in holdings:
        price = latest_price(db, h.item_code)
        unit_rial = price.close_rial if price else None
        quantity = float(h.quantity)
        value = int(unit_rial * quantity) if unit_rial else None
        item = items.get(h.item_code)

        if value:
            total_value += value
            if price and price.change_percent:
                today_change += value * price.change_percent / 100
        if h.cost_rial:
            total_cost += h.cost_rial

        rows.append(
            {
                "id": h.id,
                "item_code": h.item_code,
                "item_label": item.label_fa if item else h.item_code,
                "unit_fa": item.unit_fa if item else "",
                "quantity": quantity,
                "acquired_jalali": h.acquired_jalali,
                "cost_rial": h.cost_rial,
                "unit_price_rial": unit_rial,
                "value_rial": value,
                "change_percent": price.change_percent if price else None,
                "profit_rial": (value - h.cost_rial) if (value and h.cost_rial) else None,
                "profit_ratio": ((value - h.cost_rial) / h.cost_rial)
                if (value and h.cost_rial)
                else None,
                "price_date": price.jalali_date if price else None,
                "note": h.note,
            }
        )

    rows.sort(key=lambda r: r["value_rial"] or 0, reverse=True)
    return {
        "holdings": rows,
        "total_value_rial": total_value,
        "total_cost_rial": total_cost,
        "today_change_rial": int(today_change),
        "total_profit_rial": total_value - total_cost if total_cost else None,
        "total_profit_ratio": ((total_value - total_cost) / total_cost) if total_cost else None,
    }
