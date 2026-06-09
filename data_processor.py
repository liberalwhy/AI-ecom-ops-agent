"""Data validation, cleaning, metrics calculation and exception detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


REQUIRED_COLUMNS: dict[str, list[str]] = {
    "sku_master": [
        "sku_id",
        "spu_id",
        "product_name",
        "category",
        "variant",
        "platform",
        "price",
        "listing_status",
        "launch_date",
        "product_owner",
    ],
    "sales_daily": [
        "date",
        "platform",
        "channel",
        "sku_id",
        "sessions",
        "clicks",
        "orders",
        "units_sold",
        "gmv",
        "refunds",
        "refund_amount",
        "ad_spend",
    ],
    "inventory_daily": [
        "date",
        "sku_id",
        "warehouse",
        "available_stock",
        "locked_stock",
        "inbound_stock",
        "safety_stock",
        "lead_time_days",
        "stock_status",
    ],
    "orders": [
        "order_id",
        "order_date",
        "platform",
        "channel",
        "sku_id",
        "quantity",
        "paid_amount",
        "order_status",
        "fulfillment_status",
        "refund_status",
        "refund_amount",
        "shipping_days",
        "customer_issue",
    ],
}

NUMERIC_COLUMNS: dict[str, list[str]] = {
    "sku_master": ["price"],
    "sales_daily": [
        "sessions",
        "clicks",
        "orders",
        "units_sold",
        "gmv",
        "refunds",
        "refund_amount",
        "ad_spend",
    ],
    "inventory_daily": [
        "available_stock",
        "locked_stock",
        "inbound_stock",
        "safety_stock",
        "lead_time_days",
    ],
    "orders": ["quantity", "paid_amount", "refund_amount", "shipping_days"],
}

DATE_COLUMNS: dict[str, list[str]] = {
    "sku_master": ["launch_date"],
    "sales_daily": ["date"],
    "inventory_daily": ["date"],
    "orders": ["order_date"],
}

RISK_PRIORITY = {"高": 1, "中": 2, "低": 3, "观察": 4}


@dataclass
class ValidationResult:
    missing_fields: dict[str, list[str]]
    relation_warnings: list[str]
    duplicate_warnings: list[str]

    @property
    def has_issue(self) -> bool:
        return bool(self.missing_fields or self.relation_warnings or self.duplicate_warnings)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Return numerator / denominator and avoid ZeroDivisionError / NaN."""
    try:
        if denominator is None or float(denominator) == 0:
            return default
        value = float(numerator) / float(denominator)
        if np.isfinite(value):
            return value
    except Exception:
        return default
    return default


def read_csv_safely(source: Any) -> pd.DataFrame:
    """Read a CSV file path or Streamlit UploadedFile into a DataFrame."""
    return pd.read_csv(source, encoding="utf-8-sig")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def validate_required_fields(dataframes: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for name, required in REQUIRED_COLUMNS.items():
        df = dataframes.get(name, pd.DataFrame())
        missing_cols = [col for col in required if col not in df.columns]
        if missing_cols:
            missing[name] = missing_cols
    return missing


def validate_relations(dataframes: dict[str, pd.DataFrame]) -> list[str]:
    warnings: list[str] = []
    sku_df = dataframes.get("sku_master", pd.DataFrame())
    if "sku_id" not in sku_df.columns:
        return ["SKU 主数据表缺少 sku_id，无法进行跨表关联校验。"]

    sku_set = set(sku_df["sku_id"].dropna().astype(str))
    for name in ["sales_daily", "inventory_daily", "orders"]:
        df = dataframes.get(name, pd.DataFrame())
        if "sku_id" not in df.columns:
            continue
        unknown = sorted(set(df["sku_id"].dropna().astype(str)) - sku_set)
        if unknown:
            preview = ", ".join(unknown[:5])
            suffix = "..." if len(unknown) > 5 else ""
            warnings.append(f"{name} 中存在 {len(unknown)} 个无法在 SKU 主数据表中关联的 sku_id：{preview}{suffix}")
    return warnings


def validate_duplicates(dataframes: dict[str, pd.DataFrame]) -> list[str]:
    warnings: list[str] = []
    sku_df = dataframes.get("sku_master", pd.DataFrame())
    if "sku_id" in sku_df.columns:
        dup_count = int(sku_df["sku_id"].duplicated().sum())
        if dup_count:
            warnings.append(f"SKU 主数据表存在 {dup_count} 条重复 sku_id，系统会保留第一条用于关联。")
    return warnings


def validate_input_data(dataframes: dict[str, pd.DataFrame]) -> ValidationResult:
    normalized = {name: _normalize_columns(df) for name, df in dataframes.items()}
    return ValidationResult(
        missing_fields=validate_required_fields(normalized),
        relation_warnings=validate_relations(normalized),
        duplicate_warnings=validate_duplicates(normalized),
    )


def clean_dataframes(dataframes: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    cleaned: dict[str, pd.DataFrame] = {}
    for name, df in dataframes.items():
        frame = _normalize_columns(df)
        for col in frame.select_dtypes(include="object").columns:
            frame[col] = frame[col].astype(str).str.strip()
            frame[col] = frame[col].replace({"nan": "", "None": ""})
        for col in DATE_COLUMNS.get(name, []):
            if col in frame.columns:
                frame[col] = pd.to_datetime(frame[col], errors="coerce")
        # Add missing required fields with safe defaults so validation can warn
        # without breaking the demo page.
        for col in REQUIRED_COLUMNS.get(name, []):
            if col not in frame.columns:
                if col in NUMERIC_COLUMNS.get(name, []):
                    frame[col] = 0
                elif col in DATE_COLUMNS.get(name, []):
                    frame[col] = pd.NaT
                else:
                    frame[col] = ""
        for col in NUMERIC_COLUMNS.get(name, []):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
        if name == "sku_master" and "sku_id" in frame.columns:
            frame = frame.drop_duplicates(subset=["sku_id"], keep="first")
        cleaned[name] = frame
    return cleaned


def calculate_overall_metrics(sales_daily: pd.DataFrame) -> dict[str, float]:
    total_gmv = float(sales_daily.get("gmv", pd.Series(dtype=float)).sum())
    total_units = float(sales_daily.get("units_sold", pd.Series(dtype=float)).sum())
    total_orders = float(sales_daily.get("orders", pd.Series(dtype=float)).sum())
    total_sessions = float(sales_daily.get("sessions", pd.Series(dtype=float)).sum())
    total_refunds = float(sales_daily.get("refunds", pd.Series(dtype=float)).sum())
    total_ad_spend = float(sales_daily.get("ad_spend", pd.Series(dtype=float)).sum())
    return {
        "total_gmv": total_gmv,
        "total_units": total_units,
        "total_orders": total_orders,
        "avg_order_value": safe_divide(total_gmv, total_orders),
        "avg_conversion_rate": safe_divide(total_orders, total_sessions),
        "refund_rate": safe_divide(total_refunds, total_orders),
        "ad_roi": safe_divide(total_gmv, total_ad_spend),
        "total_sessions": total_sessions,
        "total_refunds": total_refunds,
        "total_ad_spend": total_ad_spend,
    }


def _latest_inventory(inventory_daily: pd.DataFrame) -> pd.DataFrame:
    if inventory_daily.empty or "sku_id" not in inventory_daily.columns:
        return pd.DataFrame()
    frame = inventory_daily.copy()
    if "date" in frame.columns:
        frame = frame.sort_values(["sku_id", "date"])
    return frame.groupby("sku_id", as_index=False).tail(1)


def calculate_sku_metrics(
    sku_master: pd.DataFrame,
    sales_daily: pd.DataFrame,
    inventory_daily: pd.DataFrame,
) -> pd.DataFrame:
    if sku_master.empty:
        return pd.DataFrame()

    sku_cols = [
        "sku_id",
        "spu_id",
        "product_name",
        "category",
        "variant",
        "platform",
        "price",
        "product_owner",
    ]
    sku_base = sku_master[[col for col in sku_cols if col in sku_master.columns]].copy()

    if sales_daily.empty or "sku_id" not in sales_daily.columns:
        sales_agg = pd.DataFrame({"sku_id": sku_base["sku_id"]})
    else:
        sales_agg = (
            sales_daily.groupby("sku_id", as_index=False)
            .agg(
                sku_gmv=("gmv", "sum"),
                sku_units_sold=("units_sold", "sum"),
                sku_orders=("orders", "sum"),
                sku_sessions=("sessions", "sum"),
                sku_refunds=("refunds", "sum"),
                sku_refund_amount=("refund_amount", "sum"),
                sku_ad_spend=("ad_spend", "sum"),
            )
        )
        sales_agg["sku_refund_rate"] = sales_agg.apply(
            lambda r: safe_divide(r["sku_refunds"], r["sku_orders"]), axis=1
        )
        sales_agg["sku_conversion_rate"] = sales_agg.apply(
            lambda r: safe_divide(r["sku_orders"], r["sku_sessions"]), axis=1
        )
        sales_agg["sku_ad_roi"] = sales_agg.apply(
            lambda r: safe_divide(r["sku_gmv"], r["sku_ad_spend"]), axis=1
        )

    if not sales_daily.empty and "date" in sales_daily.columns:
        latest_date = sales_daily["date"].max()
        if pd.notna(latest_date):
            recent_start = latest_date - pd.Timedelta(days=6)
            recent_sales = sales_daily[sales_daily["date"].between(recent_start, latest_date)]
        else:
            recent_sales = sales_daily.iloc[0:0]
    else:
        recent_sales = sales_daily.iloc[0:0]

    if recent_sales.empty or "sku_id" not in recent_sales.columns:
        recent_7 = pd.DataFrame({"sku_id": sku_base["sku_id"], "recent_7d_units": 0})
    else:
        recent_7 = recent_sales.groupby("sku_id", as_index=False).agg(recent_7d_units=("units_sold", "sum"))
    recent_7["avg_daily_sales_7d"] = recent_7["recent_7d_units"].fillna(0) / 7

    inv = _latest_inventory(inventory_daily)
    inv_cols = [
        "sku_id",
        "warehouse",
        "available_stock",
        "locked_stock",
        "inbound_stock",
        "safety_stock",
        "lead_time_days",
        "stock_status",
    ]
    inv = inv[[col for col in inv_cols if col in inv.columns]] if not inv.empty else pd.DataFrame({"sku_id": []})

    metrics = sku_base.merge(sales_agg, on="sku_id", how="left").merge(recent_7, on="sku_id", how="left").merge(inv, on="sku_id", how="left")

    fill_zero_cols = [
        "sku_gmv",
        "sku_units_sold",
        "sku_orders",
        "sku_sessions",
        "sku_refunds",
        "sku_refund_amount",
        "sku_ad_spend",
        "sku_refund_rate",
        "sku_conversion_rate",
        "sku_ad_roi",
        "recent_7d_units",
        "avg_daily_sales_7d",
        "available_stock",
        "locked_stock",
        "inbound_stock",
        "safety_stock",
        "lead_time_days",
    ]
    for col in fill_zero_cols:
        if col in metrics.columns:
            metrics[col] = pd.to_numeric(metrics[col], errors="coerce").fillna(0)

    metrics["stock_days"] = metrics.apply(
        lambda r: 999 if r.get("avg_daily_sales_7d", 0) <= 0 else safe_divide(r.get("available_stock", 0), r.get("avg_daily_sales_7d", 0), default=999),
        axis=1,
    )

    if "sku_units_sold" in metrics.columns and metrics["sku_units_sold"].sum() > 0:
        threshold = metrics["sku_units_sold"].quantile(0.8)
        metrics["is_hot_sku"] = metrics["sku_units_sold"] >= threshold
    else:
        metrics["is_hot_sku"] = False

    return metrics


def _risk_action(reasons: list[str]) -> str:
    if any("热销缺货" in r for r in reasons):
        return "建议供应链确认在途库存和补货时间；运营根据库存情况调整投放节奏；销售准备替代 SKU 推荐方案。"
    if any("滞销积压" in r for r in reasons):
        return "建议商品与运营复盘卖点、价格和渠道流量，制定促销、组合销售或清仓策略。"
    if any("库存不足" in r for r in reasons):
        return "建议供应链确认可用库存和补货排期，客服提前准备缺货或延迟发货话术。"
    return "建议持续观察销售节奏与库存变化，必要时调整补货和投放策略。"


def identify_inventory_risks(sku_metrics: pd.DataFrame) -> pd.DataFrame:
    if sku_metrics.empty:
        return pd.DataFrame(
            columns=[
                "sku_id",
                "product_name",
                "available_stock",
                "safety_stock",
                "lead_time_days",
                "avg_daily_sales_7d",
                "stock_days",
                "risk_level",
                "risk_reason",
                "suggested_action",
            ]
        )

    risk_rows: list[dict] = []
    for _, row in sku_metrics.iterrows():
        available_stock = float(row.get("available_stock", 0))
        safety_stock = float(row.get("safety_stock", 0))
        lead_time_days = float(row.get("lead_time_days", 0))
        avg_daily_sales_7d = float(row.get("avg_daily_sales_7d", 0))
        stock_days = float(row.get("stock_days", 999))
        is_hot = bool(row.get("is_hot_sku", False))

        reasons: list[str] = []
        risk_level = None

        high_stockout = available_stock <= safety_stock or stock_days <= lead_time_days
        medium_stockout = stock_days <= lead_time_days + 3 or available_stock <= safety_stock * 1.5
        hot_stockout = is_hot and stock_days < lead_time_days + 3
        slow_overstock = avg_daily_sales_7d < 3 and stock_days > 60

        if hot_stockout:
            reasons.append("热销缺货风险：热销 SKU 的预计可售天数低于补货周期 + 3 天。")
            risk_level = "高"
        if high_stockout:
            reasons.append("高风险库存不足：可售库存低于安全库存或预计可售天数低于补货周期。")
            risk_level = "高"
        if not risk_level and medium_stockout:
            reasons.append("中风险库存不足：预计可售天数接近补货周期，或可售库存接近安全库存。")
            risk_level = "中"
        if slow_overstock:
            reasons.append("滞销积压：近 7 日日均销量低于 3 件，且预计可售天数超过 60 天。")
            risk_level = risk_level or "中"

        if reasons:
            risk_rows.append(
                {
                    "sku_id": row.get("sku_id", ""),
                    "product_name": row.get("product_name", ""),
                    "available_stock": round(available_stock, 2),
                    "safety_stock": round(safety_stock, 2),
                    "lead_time_days": round(lead_time_days, 2),
                    "avg_daily_sales_7d": round(avg_daily_sales_7d, 2),
                    "stock_days": round(stock_days, 1) if stock_days < 999 else 999,
                    "risk_level": risk_level or "观察",
                    "risk_reason": "；".join(reasons),
                    "suggested_action": _risk_action(reasons),
                }
            )

    risks = pd.DataFrame(risk_rows)
    if not risks.empty:
        risks["risk_sort"] = risks["risk_level"].map(RISK_PRIORITY).fillna(9)
        risks = risks.sort_values(["risk_sort", "stock_days", "available_stock"], ascending=[True, True, True]).drop(columns=["risk_sort"])
    return risks


def _attach_product_name(df: pd.DataFrame, sku_master: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    sku_cols = ["sku_id", "product_name"]
    if "sku_id" in sku_master.columns and "product_name" in sku_master.columns:
        return df.merge(sku_master[sku_cols].drop_duplicates("sku_id"), on="sku_id", how="left")
    df["product_name"] = ""
    return df


def _append_exception(
    rows: list[dict],
    exception_type: str,
    sku_id: str,
    product_name: str,
    exception_count: int,
    risk_reason: str,
    suggested_action: str,
) -> None:
    if exception_count > 0:
        rows.append(
            {
                "exception_type": exception_type,
                "sku_id": sku_id,
                "product_name": product_name,
                "exception_count": int(exception_count),
                "risk_reason": risk_reason,
                "suggested_action": suggested_action,
            }
        )


def identify_order_exceptions(
    orders: pd.DataFrame,
    sku_metrics: pd.DataFrame,
    sku_master: pd.DataFrame,
) -> pd.DataFrame:
    columns = ["exception_type", "sku_id", "product_name", "exception_count", "risk_reason", "suggested_action"]
    if orders.empty or "sku_id" not in orders.columns:
        return pd.DataFrame(columns=columns)

    sku_name = (
        sku_master[["sku_id", "product_name"]].drop_duplicates("sku_id").set_index("sku_id")["product_name"].to_dict()
        if {"sku_id", "product_name"}.issubset(sku_master.columns)
        else {}
    )
    rows: list[dict] = []

    # 1. Delayed shipping: shipping_days > 3.
    if "shipping_days" in orders.columns:
        delayed = orders[pd.to_numeric(orders["shipping_days"], errors="coerce").fillna(0) > 3]
        for sku_id, cnt in delayed.groupby("sku_id").size().items():
            _append_exception(
                rows,
                "延迟发货",
                sku_id,
                sku_name.get(sku_id, ""),
                int(cnt),
                "存在发货耗时超过 3 天的订单，可能影响客户体验和平台履约评分。",
                "建议供应链和仓配团队核查拣货、打包、出库节点；客服提前同步物流延迟解释话术。",
            )

    # 2. Refund abnormal: SKU refund rate > 5%.
    if not sku_metrics.empty and "sku_refund_rate" in sku_metrics.columns:
        abnormal_refund = sku_metrics[sku_metrics["sku_refund_rate"] > 0.05]
        for _, r in abnormal_refund.iterrows():
            _append_exception(
                rows,
                "退款异常",
                str(r.get("sku_id", "")),
                str(r.get("product_name", "")),
                int(r.get("sku_refunds", 0)),
                f"SKU 退款率为 {safe_divide(r.get('sku_refunds', 0), r.get('sku_orders', 0)):.1%}，高于 5% 阈值。",
                "建议商品、客服和运营共同复盘退款原因，优先排查质量、描述、物流和使用门槛问题。",
            )

    # 3. Pending payment abnormal: pending payment ratio > 15% per SKU.
    if "order_status" in orders.columns:
        status_agg = orders.groupby("sku_id").agg(
            total_orders=("order_id", "count"),
            pending_orders=("order_status", lambda s: int((s == "待付款").sum())),
        )
        status_agg["pending_ratio"] = status_agg.apply(
            lambda r: safe_divide(r["pending_orders"], r["total_orders"]), axis=1
        )
        abnormal_pending = status_agg[status_agg["pending_ratio"] > 0.15]
        for sku_id, r in abnormal_pending.iterrows():
            _append_exception(
                rows,
                "待付款异常",
                str(sku_id),
                sku_name.get(sku_id, ""),
                int(r["pending_orders"]),
                f"待付款订单占比为 {r['pending_ratio']:.1%}，高于 15% 阈值。",
                "建议运营检查价格、优惠、支付链路和客服催付策略，必要时针对高意向用户做二次触达。",
            )

    # 4. Fulfillment abnormal: paid but pending shipping for too long.
    if {"order_status", "fulfillment_status", "shipping_days"}.issubset(orders.columns):
        fulfillment = orders[
            (orders["order_status"] == "已付款")
            & (orders["fulfillment_status"].isin(["待发货", "未履约"]))
            & (pd.to_numeric(orders["shipping_days"], errors="coerce").fillna(0) >= 3)
        ]
        for sku_id, cnt in fulfillment.groupby("sku_id").size().items():
            _append_exception(
                rows,
                "履约异常",
                str(sku_id),
                sku_name.get(sku_id, ""),
                int(cnt),
                "存在已付款但长期待发货订单，需关注库存锁定、仓库履约和系统状态同步。",
                "建议仓配优先核对待发货订单；运营同步风险 SKU；客服准备订单进度解释和补偿策略。",
            )

    # 5. After-sales abnormal: concentrated customer issues.
    if "customer_issue" in orders.columns:
        issue_keywords = ["质量问题", "物流延迟", "缺件", "不会使用"]
        for keyword in issue_keywords:
            issue_df = orders[orders["customer_issue"].astype(str).str.contains(keyword, na=False)]
            issue_counts = issue_df.groupby("sku_id").size().sort_values(ascending=False)
            for sku_id, cnt in issue_counts[issue_counts >= 3].items():
                _append_exception(
                    rows,
                    f"售后异常-{keyword}",
                    str(sku_id),
                    sku_name.get(sku_id, ""),
                    int(cnt),
                    f"用户问题中集中出现“{keyword}”，需要判断是否为商品、物流或说明文档问题。",
                    "建议客服沉淀标准回复；商品团队补充说明材料；运营在详情页或直播脚本中提前解释高频问题。",
                )

    result = pd.DataFrame(rows, columns=columns)
    if not result.empty:
        result = result.sort_values(["exception_count", "exception_type"], ascending=[False, True])
    return result


def calculate_platform_channel_metrics(sales_daily: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if sales_daily.empty:
        return {"platform": pd.DataFrame(), "channel": pd.DataFrame()}

    platform = (
        sales_daily.groupby("platform", as_index=False)
        .agg(gmv=("gmv", "sum"), orders=("orders", "sum"), sessions=("sessions", "sum"), ad_spend=("ad_spend", "sum"))
    )
    platform["conversion_rate"] = platform.apply(lambda r: safe_divide(r["orders"], r["sessions"]), axis=1)
    platform["ad_roi"] = platform.apply(lambda r: safe_divide(r["gmv"], r["ad_spend"]), axis=1)
    platform = platform.sort_values("gmv", ascending=False)

    channel = (
        sales_daily.groupby(["platform", "channel"], as_index=False)
        .agg(gmv=("gmv", "sum"), orders=("orders", "sum"), units_sold=("units_sold", "sum"), sessions=("sessions", "sum"))
    )
    channel["conversion_rate"] = channel.apply(lambda r: safe_divide(r["orders"], r["sessions"]), axis=1)
    channel = channel.sort_values("gmv", ascending=False)
    return {"platform": platform, "channel": channel}


def analyze_ecom_ops(
    sku_master: pd.DataFrame,
    sales_daily: pd.DataFrame,
    inventory_daily: pd.DataFrame,
    orders: pd.DataFrame,
) -> dict[str, Any]:
    raw = {
        "sku_master": sku_master,
        "sales_daily": sales_daily,
        "inventory_daily": inventory_daily,
        "orders": orders,
    }
    validation = validate_input_data(raw)
    cleaned = clean_dataframes(raw)

    overall = calculate_overall_metrics(cleaned["sales_daily"])
    sku_metrics = calculate_sku_metrics(cleaned["sku_master"], cleaned["sales_daily"], cleaned["inventory_daily"])
    inventory_risks = identify_inventory_risks(sku_metrics)
    order_exceptions = identify_order_exceptions(cleaned["orders"], sku_metrics, cleaned["sku_master"])
    platform_channel = calculate_platform_channel_metrics(cleaned["sales_daily"])

    overall["inventory_risk_sku_count"] = int(inventory_risks["sku_id"].nunique()) if not inventory_risks.empty else 0
    overall["order_exception_count"] = int(order_exceptions["exception_count"].sum()) if not order_exceptions.empty else 0

    return {
        "validation": validation,
        "data": cleaned,
        "overall_metrics": overall,
        "sku_metrics": sku_metrics,
        "inventory_risks": inventory_risks,
        "order_exceptions": order_exceptions,
        "platform_metrics": platform_channel["platform"],
        "channel_metrics": platform_channel["channel"],
    }


def format_percent(value: float) -> str:
    return f"{value:.2%}"


def format_currency(value: float) -> str:
    return f"¥{value:,.0f}"
