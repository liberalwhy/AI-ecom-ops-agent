"""Generate sample e-commerce operations data for Ecom Ops Agent.

The generated data intentionally contains several business scenarios:
- Hot-selling SKU with stockout risk
- Slow-moving SKU with overstock
- High refund-rate SKU
- Fast-growing channel
- Low conversion platform
- Delayed shipment orders
- High ad spend but low ROI SKU
- High pending-payment ratio
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


BASE_DATE = pd.Timestamp("2026-06-09")
RANDOM_SEED = 42


def _sku_rows() -> list[dict]:
    products = [
        ("CAM-X4-BLK-STD", "CAM-X4", "运动相机 X4", "运动相机", "黑色标准版", "天猫", 2999, "在售", "商品组A"),
        ("CAM-X4-WHT-PRO", "CAM-X4", "运动相机 X4", "运动相机", "白色专业版", "京东", 3699, "在售", "商品组A"),
        ("GMB-ALPHA-BLK", "GMB-ALPHA", "游戏掌机 Alpha", "数码配件", "黑色 512G", "抖音", 2499, "在售", "商品组B"),
        ("GMB-ALPHA-WHT", "GMB-ALPHA", "游戏掌机 Alpha", "数码配件", "白色 512G", "天猫", 2499, "在售", "商品组B"),
        ("DRN-MINI-STD", "DRN-MINI", "航拍无人机 Mini", "无人机", "标准版", "京东", 4599, "在售", "商品组C"),
        ("DRN-MINI-CMB", "DRN-MINI", "航拍无人机 Mini", "无人机", "畅飞套装", "天猫", 5599, "在售", "商品组C"),
        ("VAC-S9-WHT", "VAC-S9", "智能洗地机 S9", "家用电器", "白色", "拼多多", 1899, "在售", "商品组D"),
        ("VAC-S9-GRY", "VAC-S9", "智能洗地机 S9", "家用电器", "灰色", "京东", 1899, "在售", "商品组D"),
        ("SPK-BASS-BLK", "SPK-BASS", "蓝牙音箱 Bass", "音频设备", "黑色", "天猫", 699, "在售", "商品组E"),
        ("SPK-BASS-RED", "SPK-BASS", "蓝牙音箱 Bass", "音频设备", "红色", "抖音", 699, "在售", "商品组E"),
        ("LGT-PRO-XL", "LGT-PRO", "直播补光灯 Pro", "直播设备", "XL", "抖音", 399, "在售", "商品组F"),
        ("LGT-PRO-M", "LGT-PRO", "直播补光灯 Pro", "直播设备", "M", "天猫", 299, "在售", "商品组F"),
        ("KBD-MECH-BLK", "KBD-MECH", "机械键盘 K1", "办公外设", "黑轴", "京东", 499, "在售", "商品组G"),
        ("KBD-MECH-BLU", "KBD-MECH", "机械键盘 K1", "办公外设", "青轴", "天猫", 499, "在售", "商品组G"),
        ("MSE-AIR-WHT", "MSE-AIR", "无线鼠标 Air", "办公外设", "白色", "拼多多", 199, "在售", "商品组G"),
        ("MSE-AIR-BLK", "MSE-AIR", "无线鼠标 Air", "办公外设", "黑色", "京东", 199, "在售", "商品组G"),
        ("BAG-CAM-L", "BAG-CAM", "相机收纳包", "配件", "大号", "天猫", 159, "在售", "商品组H"),
        ("BAG-CAM-S", "BAG-CAM", "相机收纳包", "配件", "小号", "京东", 129, "在售", "商品组H"),
        ("TRI-MINI", "TRI-MINI", "迷你三脚架", "配件", "便携版", "抖音", 99, "在售", "商品组H"),
        ("CHG-FAST-65W", "CHG-FAST", "65W 快充头", "配件", "白色", "拼多多", 129, "在售", "商品组H"),
    ]
    rows: list[dict] = []
    for i, item in enumerate(products):
        sku_id, spu_id, product_name, category, variant, platform, price, status, owner = item
        rows.append(
            {
                "sku_id": sku_id,
                "spu_id": spu_id,
                "product_name": product_name,
                "category": category,
                "variant": variant,
                "platform": platform,
                "price": price,
                "listing_status": status,
                "launch_date": (BASE_DATE - pd.Timedelta(days=8 + i * 3)).strftime("%Y-%m-%d"),
                "product_owner": owner,
            }
        )
    return rows


def generate_sku_master() -> pd.DataFrame:
    """Create the 20-row SKU master table."""
    return pd.DataFrame(_sku_rows())


def generate_sales_daily(sku_master: pd.DataFrame, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate 14 days of daily sales for each SKU."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(BASE_DATE - pd.Timedelta(days=13), BASE_DATE, freq="D")

    channel_map = {
        "天猫": ["自然搜索", "品牌广告", "直播间"],
        "京东": ["站内推荐", "品牌广告", "搜索广告"],
        "抖音": ["短视频", "直播间", "达人分销"],
        "拼多多": ["活动会场", "搜索广告", "自然流量"],
    }

    # base units, conversion and ad spend patterns per SKU.
    sku_patterns = {
        "CAM-X4-BLK-STD": (36, 0.065, 4200),   # hot-selling stockout risk
        "CAM-X4-WHT-PRO": (15, 0.038, 2600),
        "GMB-ALPHA-BLK": (8, 0.032, 16000),    # high ad spend, low ROI
        "GMB-ALPHA-WHT": (12, 0.042, 1900),
        "DRN-MINI-STD": (5, 0.018, 3000),      # low conversion on JD
        "DRN-MINI-CMB": (6, 0.023, 2500),
        "VAC-S9-WHT": (22, 0.052, 1600),       # channel growth
        "VAC-S9-GRY": (9, 0.028, 900),
        "SPK-BASS-BLK": (18, 0.049, 700),
        "SPK-BASS-RED": (12, 0.045, 600),
        "LGT-PRO-XL": (10, 0.037, 550),
        "LGT-PRO-M": (11, 0.041, 520),
        "KBD-MECH-BLK": (14, 0.044, 900),
        "KBD-MECH-BLU": (7, 0.025, 850),       # high refund rate
        "MSE-AIR-WHT": (16, 0.050, 480),
        "MSE-AIR-BLK": (13, 0.046, 420),
        "BAG-CAM-L": (2, 0.016, 180),          # slow-moving overstock
        "BAG-CAM-S": (3, 0.020, 160),
        "TRI-MINI": (11, 0.050, 200),
        "CHG-FAST-65W": (17, 0.054, 260),
    }

    rows: list[dict] = []
    for _, sku in sku_master.iterrows():
        sku_id = sku["sku_id"]
        platform = sku["platform"]
        price = float(sku["price"])
        base_units, base_cvr, base_ad = sku_patterns[sku_id]

        for idx, date in enumerate(dates):
            weekday_factor = 1.15 if date.dayofweek in [4, 5, 6] else 1.0
            noise = rng.normal(1.0, 0.12)
            trend = 1.0

            # Channel growth: Douyin live/short-video growth on VAC-S9-WHT and CAM-X4-BLK-STD.
            if sku_id in {"VAC-S9-WHT", "CAM-X4-BLK-STD"}:
                trend = 0.75 + idx * 0.055

            # Low conversion platform scenario: some JD SKUs have high traffic but low orders.
            sessions_factor = 1.0
            if platform == "京东" and sku_id in {"DRN-MINI-STD", "GMB-ALPHA-BLK"}:
                sessions_factor = 1.9

            units = max(0, int(round(base_units * weekday_factor * noise * trend)))
            orders = max(0, int(round(units / rng.uniform(1.02, 1.25))))
            sessions = max(orders, int(round(orders / max(base_cvr * rng.uniform(0.85, 1.15), 0.005) * sessions_factor)))
            clicks = max(orders, int(round(sessions * rng.uniform(0.12, 0.22))))
            gmv = round(units * price * rng.uniform(0.92, 1.02), 2)

            refund_rate = 0.018
            if sku_id == "KBD-MECH-BLU":
                refund_rate = 0.095
            elif sku_id == "CAM-X4-BLK-STD":
                refund_rate = 0.028
            elif sku_id == "GMB-ALPHA-BLK":
                refund_rate = 0.055

            refunds = int(round(orders * refund_rate * rng.uniform(0.7, 1.3)))
            refund_amount = round(refunds * price * rng.uniform(0.85, 1.0), 2)

            channel_choices = channel_map[platform]
            if sku_id in {"VAC-S9-WHT", "CAM-X4-BLK-STD"} and idx >= 7:
                channel = "直播间" if platform in {"天猫", "抖音"} else channel_choices[0]
            else:
                channel = rng.choice(channel_choices)

            ad_spend = round(base_ad * rng.uniform(0.75, 1.25), 2)
            if sku_id == "GMB-ALPHA-BLK":
                ad_spend = round(base_ad * rng.uniform(1.2, 1.65), 2)

            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "platform": platform,
                    "channel": channel,
                    "sku_id": sku_id,
                    "sessions": sessions,
                    "clicks": clicks,
                    "orders": orders,
                    "units_sold": units,
                    "gmv": gmv,
                    "refunds": refunds,
                    "refund_amount": refund_amount,
                    "ad_spend": ad_spend,
                }
            )

    return pd.DataFrame(rows)


def generate_inventory_daily(sku_master: pd.DataFrame) -> pd.DataFrame:
    """Generate one inventory snapshot for each SKU."""
    inventory_plan = {
        "CAM-X4-BLK-STD": (96, 18, 120, 110, 7, "偏低"),     # hot-selling stockout risk
        "CAM-X4-WHT-PRO": (180, 10, 90, 80, 9, "正常"),
        "GMB-ALPHA-BLK": (230, 8, 40, 75, 10, "正常"),
        "GMB-ALPHA-WHT": (140, 6, 60, 60, 8, "正常"),
        "DRN-MINI-STD": (95, 3, 35, 50, 14, "正常"),
        "DRN-MINI-CMB": (86, 4, 30, 45, 14, "正常"),
        "VAC-S9-WHT": (92, 12, 50, 75, 8, "偏低"),
        "VAC-S9-GRY": (170, 6, 50, 70, 8, "正常"),
        "SPK-BASS-BLK": (210, 9, 100, 90, 6, "正常"),
        "SPK-BASS-RED": (160, 4, 70, 70, 6, "正常"),
        "LGT-PRO-XL": (240, 5, 80, 65, 5, "正常"),
        "LGT-PRO-M": (260, 7, 70, 65, 5, "正常"),
        "KBD-MECH-BLK": (135, 6, 80, 60, 7, "正常"),
        "KBD-MECH-BLU": (310, 4, 50, 60, 7, "正常"),
        "MSE-AIR-WHT": (190, 8, 80, 75, 5, "正常"),
        "MSE-AIR-BLK": (210, 5, 60, 75, 5, "正常"),
        "BAG-CAM-L": (480, 2, 0, 45, 4, "积压"),             # slow-moving overstock
        "BAG-CAM-S": (370, 1, 0, 35, 4, "积压"),
        "TRI-MINI": (160, 10, 60, 55, 4, "正常"),
        "CHG-FAST-65W": (240, 9, 80, 70, 4, "正常"),
    }
    warehouses = ["华东仓", "华南仓", "华北仓"]
    rows = []
    for idx, sku_id in enumerate(sku_master["sku_id"]):
        available, locked, inbound, safety, lead_time, status = inventory_plan[sku_id]
        rows.append(
            {
                "date": BASE_DATE.strftime("%Y-%m-%d"),
                "sku_id": sku_id,
                "warehouse": warehouses[idx % len(warehouses)],
                "available_stock": available,
                "locked_stock": locked,
                "inbound_stock": inbound,
                "safety_stock": safety,
                "lead_time_days": lead_time,
                "stock_status": status,
            }
        )
    return pd.DataFrame(rows)


def generate_orders(
    sku_master: pd.DataFrame,
    sales_daily: pd.DataFrame,
    seed: int = RANDOM_SEED,
    target_orders: int = 420,
) -> pd.DataFrame:
    """Generate 300-500 order rows with explicit abnormal scenarios."""
    rng = np.random.default_rng(seed + 7)
    sku_lookup = sku_master.set_index("sku_id").to_dict("index")
    sales_weights = sales_daily.groupby("sku_id")["orders"].sum()
    weights = sales_weights / sales_weights.sum()
    sku_ids = weights.index.to_numpy()

    channels_by_platform = {
        "天猫": ["自然搜索", "品牌广告", "直播间"],
        "京东": ["站内推荐", "品牌广告", "搜索广告"],
        "抖音": ["短视频", "直播间", "达人分销"],
        "拼多多": ["活动会场", "搜索广告", "自然流量"],
    }
    issue_pool = ["无", "无", "无", "物流延迟", "质量问题", "不会使用", "缺件", "尺码/规格理解偏差"]

    rows: list[dict] = []
    for i in range(target_orders):
        sku_id = str(rng.choice(sku_ids, p=weights.to_numpy()))
        sku = sku_lookup[sku_id]
        platform = sku["platform"]
        channel = str(rng.choice(channels_by_platform[platform]))
        order_date = BASE_DATE - pd.Timedelta(days=int(rng.integers(0, 14)))
        quantity = int(rng.choice([1, 1, 1, 2, 2, 3], p=[0.56, 0.18, 0.10, 0.10, 0.04, 0.02]))
        paid_amount = round(quantity * float(sku["price"]) * rng.uniform(0.88, 1.0), 2)

        # Pending-payment abnormal scenario for DRN-MINI-STD and GMB-ALPHA-BLK.
        pending_prob = 0.05
        if sku_id in {"DRN-MINI-STD", "GMB-ALPHA-BLK"}:
            pending_prob = 0.23
        order_status = "待付款" if rng.random() < pending_prob else "已付款"

        fulfillment_status = "已发货"
        shipping_days = int(rng.choice([1, 1, 2, 2, 3], p=[0.28, 0.22, 0.25, 0.15, 0.10]))

        # Delayed shipment scenario.
        if sku_id in {"CAM-X4-BLK-STD", "VAC-S9-WHT", "KBD-MECH-BLU"} and rng.random() < 0.28:
            shipping_days = int(rng.choice([4, 5, 6, 7], p=[0.35, 0.30, 0.20, 0.15]))
            fulfillment_status = "已发货" if rng.random() < 0.78 else "待发货"

        if order_status == "待付款":
            fulfillment_status = "未履约"
            shipping_days = 0

        # Fulfillment abnormal: paid but still pending shipping.
        if order_status == "已付款" and sku_id in {"CAM-X4-BLK-STD", "VAC-S9-WHT"} and rng.random() < 0.08:
            fulfillment_status = "待发货"
            shipping_days = int(rng.choice([4, 5, 6]))

        refund_prob = 0.025
        if sku_id == "KBD-MECH-BLU":
            refund_prob = 0.14
        elif sku_id == "GMB-ALPHA-BLK":
            refund_prob = 0.075
        refund_status = "已退款" if order_status == "已付款" and rng.random() < refund_prob else "未退款"
        refund_amount = round(paid_amount * rng.uniform(0.55, 1.0), 2) if refund_status == "已退款" else 0.0

        customer_issue = "无"
        if refund_status == "已退款":
            customer_issue = "质量问题" if sku_id == "KBD-MECH-BLU" else str(rng.choice(["物流延迟", "不会使用", "缺件"]))
        elif shipping_days > 3:
            customer_issue = "物流延迟"
        elif rng.random() < 0.06:
            customer_issue = str(rng.choice(issue_pool))

        rows.append(
            {
                "order_id": f"OD{BASE_DATE.strftime('%Y%m%d')}{i + 1:05d}",
                "order_date": order_date.strftime("%Y-%m-%d"),
                "platform": platform,
                "channel": channel,
                "sku_id": sku_id,
                "quantity": quantity,
                "paid_amount": paid_amount if order_status == "已付款" else 0.0,
                "order_status": order_status,
                "fulfillment_status": fulfillment_status,
                "refund_status": refund_status,
                "refund_amount": refund_amount,
                "shipping_days": shipping_days,
                "customer_issue": customer_issue,
            }
        )

    return pd.DataFrame(rows)


def generate_all(output_dir: str | Path = "sample_data", seed: int = RANDOM_SEED) -> dict[str, pd.DataFrame]:
    """Generate all sample CSV files into the target directory."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    sku_master = generate_sku_master()
    sales_daily = generate_sales_daily(sku_master, seed=seed)
    inventory_daily = generate_inventory_daily(sku_master)
    orders = generate_orders(sku_master, sales_daily, seed=seed)

    frames = {
        "sku_master": sku_master,
        "sales_daily": sales_daily,
        "inventory_daily": inventory_daily,
        "orders": orders,
    }
    for name, frame in frames.items():
        frame.to_csv(output_path / f"{name}.csv", index=False, encoding="utf-8-sig")
    return frames


if __name__ == "__main__":
    generate_all()
    print("Sample data generated in ./sample_data")
