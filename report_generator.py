"""Template-based report generation for Ecom Ops Agent.

Current version does not call any LLM API. The functions here are intentionally
structured as an independent report layer, so future versions can replace the
rule/template engine with OpenAI, DeepSeek, Kimi or another OpenAI-compatible API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from data_processor import format_currency, format_percent, safe_divide


ROLE_ACTIONS = {
    "运营": [
        "复盘高 GMV SKU 的流量来源、转化链路和投放节奏。",
        "对库存风险 SKU 控制投放节奏，避免持续放量导致断货。",
        "对低 ROI SKU 检查投放计划、素材卖点和关键词结构。",
    ],
    "供应链": [
        "确认高风险 SKU 的可售库存、锁定库存、在途库存和预计到货时间。",
        "对预计可售天数低于补货周期的 SKU 提前安排补货或调拨。",
    ],
    "客服": [
        "针对延迟发货、缺货和退款高发 SKU 准备统一沟通话术。",
        "将高频售后问题反馈给商品与运营，补充详情页说明和使用指引。",
    ],
    "销售": [
        "对热销缺货 SKU 准备替代款推荐方案。",
        "对高意向未支付订单配合运营做二次触达。",
    ],
    "商品": [
        "复盘退款率偏高 SKU 的商品描述、质量反馈和规格理解问题。",
        "对滞销积压 SKU 制定组合销售、价格调整或清仓方案。",
    ],
}


def _df_has_rows(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def _top_row(df: pd.DataFrame, sort_col: str) -> dict[str, Any] | None:
    if not _df_has_rows(df) or sort_col not in df.columns:
        return None
    return df.sort_values(sort_col, ascending=False).iloc[0].to_dict()


def _markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 10) -> str:
    if not _df_has_rows(df):
        return "当前数据不足以判断。"
    available_cols = [col for col in columns if col in df.columns]
    if not available_cols:
        return "当前数据不足以判断。"
    table = df[available_cols].head(max_rows).copy()
    for col in table.columns:
        if "rate" in col or "率" in col:
            table[col] = table[col].apply(lambda x: f"{float(x):.2%}" if pd.notna(x) else "")
        elif col in {"sku_gmv", "gmv", "paid_amount", "refund_amount", "sku_ad_spend"}:
            table[col] = table[col].apply(lambda x: f"¥{float(x):,.0f}" if pd.notna(x) else "")
        else:
            table[col] = table[col].apply(lambda x: "" if pd.isna(x) else str(x))

    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(table.columns)) + " |"
    rows = [
        "| " + " | ".join(str(value).replace("\n", " ") for value in row) + " |"
        for row in table.to_numpy()
    ]
    return "\n".join([header, separator, *rows])


def build_key_findings(results: dict[str, Any]) -> list[str]:
    metrics = results.get("overall_metrics", {})
    sku_metrics = results.get("sku_metrics", pd.DataFrame())
    inventory_risks = results.get("inventory_risks", pd.DataFrame())
    order_exceptions = results.get("order_exceptions", pd.DataFrame())
    platform_metrics = results.get("platform_metrics", pd.DataFrame())

    findings: list[str] = []
    if metrics:
        findings.append(
            f"整体 GMV {format_currency(metrics.get('total_gmv', 0))}，销量 {metrics.get('total_units', 0):,.0f} 件，订单 {metrics.get('total_orders', 0):,.0f} 单，平均转化率 {format_percent(metrics.get('avg_conversion_rate', 0))}。"
        )
    else:
        findings.append("当前销售数据不足以判断整体经营表现。")

    top_sku = _top_row(sku_metrics, "sku_gmv")
    if top_sku:
        findings.append(
            f"GMV 贡献最高 SKU 为 {top_sku.get('product_name', '')}（{top_sku.get('sku_id', '')}），GMV {format_currency(top_sku.get('sku_gmv', 0))}，销量 {top_sku.get('sku_units_sold', 0):,.0f} 件。"
        )

    if _df_has_rows(inventory_risks):
        high_count = int((inventory_risks["risk_level"] == "高").sum()) if "risk_level" in inventory_risks.columns else 0
        first = inventory_risks.iloc[0].to_dict()
        findings.append(
            f"库存风险 SKU 共 {inventory_risks['sku_id'].nunique()} 个，其中高风险 {high_count} 个；首要关注 {first.get('product_name', '')}（{first.get('sku_id', '')}），预计可售 {first.get('stock_days', '未知')} 天。"
        )
    else:
        findings.append("当前未识别到明确库存风险 SKU。")

    if _df_has_rows(order_exceptions):
        first_ex = order_exceptions.iloc[0].to_dict()
        findings.append(
            f"订单异常共 {int(order_exceptions['exception_count'].sum())} 条，主要类型为 {first_ex.get('exception_type', '')}，首要 SKU 为 {first_ex.get('product_name', '')}（{first_ex.get('sku_id', '')}）。"
        )
    else:
        findings.append("当前未识别到明显订单异常。")

    if _df_has_rows(platform_metrics):
        low_cvr = platform_metrics.sort_values("conversion_rate", ascending=True).iloc[0]
        findings.append(
            f"平台层面需关注 {low_cvr.get('platform', '')} 转化率偏低，当前转化率 {format_percent(low_cvr.get('conversion_rate', 0))}。"
        )
    return findings


def generate_feishu_notice(results: dict[str, Any]) -> str:
    inventory_risks = results.get("inventory_risks", pd.DataFrame())
    order_exceptions = results.get("order_exceptions", pd.DataFrame())
    sku_metrics = results.get("sku_metrics", pd.DataFrame())
    metrics = results.get("overall_metrics", {})

    lines = ["【今日运营异常提醒】"]
    if _df_has_rows(inventory_risks):
        r = inventory_risks.iloc[0]
        lines.append(
            f"今日需优先关注 {r.get('product_name', '')}（{r.get('sku_id', '')}）：当前可售库存 {r.get('available_stock', 0):.0f} 件，预计可售约 {r.get('stock_days', 0)} 天，补货周期 {r.get('lead_time_days', 0):.0f} 天，风险等级：{r.get('risk_level', '')}。"
        )
        lines.append("建议供应链同学确认在途库存和到货时间，运营同学同步调整投放节奏，销售和客服准备替代 SKU 推荐及沟通话术。")
    elif _df_has_rows(order_exceptions):
        e = order_exceptions.iloc[0]
        lines.append(
            f"今日订单异常主要集中在 {e.get('product_name', '')}（{e.get('sku_id', '')}），异常类型：{e.get('exception_type', '')}，异常订单 {e.get('exception_count', 0)} 条。建议相关团队优先跟进。"
        )
    elif _df_has_rows(sku_metrics):
        top = sku_metrics.sort_values("sku_gmv", ascending=False).iloc[0]
        lines.append(
            f"今日整体经营相对平稳，GMV {format_currency(metrics.get('total_gmv', 0))}。GMV TOP SKU 为 {top.get('product_name', '')}（{top.get('sku_id', '')}）。建议继续观察库存、退款和履约状态。"
        )
    else:
        lines.append("当前数据不足以判断，请补充 SKU、销售、库存和订单数据后重新生成。")
    return "\n".join(lines)


def generate_sop_suggestions(results: dict[str, Any]) -> str:
    inventory_risks = results.get("inventory_risks", pd.DataFrame())
    order_exceptions = results.get("order_exceptions", pd.DataFrame())

    sections: list[str] = ["# SOP / 复盘沉淀建议"]

    def add_hot_stockout_sop() -> None:
        sections.extend(
            [
                "\n## 一、场景名称：热销 SKU 库存不足",
                "\n### 触发条件",
                "- SKU 属于热销 SKU 或近 7 日销量明显高于其他 SKU。",
                "- 可售库存低于安全库存，或预计可售天数低于补货周期。",
                "- 相关 SKU 仍处于广告投放、直播推荐或活动承接状态。",
                "\n### 处理步骤",
                "1. 运营确认销量增长来源，包括渠道、活动、广告和直播间贡献。",
                "2. 供应链确认可售库存、锁定库存、在途库存和预计到货日期。",
                "3. 商品团队确认是否有可替代 SKU 或相近规格可推荐。",
                "4. 销售团队同步替代 SKU 推荐方案。",
                "5. 客服提前准备缺货、延迟发货和替代款沟通话术。",
                "6. 运营根据库存覆盖天数调整投放节奏，必要时降低预算或暂停活动位。",
                "\n### 需要同步的角色",
                "- 运营\n- 供应链\n- 商品\n- 销售\n- 客服",
                "\n### 复盘记录字段",
                "- sku_id\n- 触发日期\n- 近 7 日日均销量\n- 可售库存\n- 安全库存\n- 预计可售天数\n- 补货周期\n- 实际到货日期\n- 投放调整动作\n- 是否发生断货",
                "\n### 后续优化建议",
                "- 将“预计可售天数 < 补货周期 + 3 天”沉淀为日常库存预警规则。",
                "- 对活动 SKU 建立活动前库存校验清单。",
            ]
        )

    def add_refund_sop() -> None:
        sections.extend(
            [
                "\n## 二、场景名称：退款率异常",
                "\n### 触发条件",
                "- SKU 退款率高于 5%。",
                "- 售后问题集中出现质量问题、物流延迟、缺件或不会使用。",
                "\n### 处理步骤",
                "1. 客服导出退款原因和售后工单，按问题类型归类。",
                "2. 商品团队排查商品质量、规格描述、配件完整性和使用门槛。",
                "3. 运营检查详情页、直播脚本和广告素材是否存在预期偏差。",
                "4. 仓配团队检查包装、出库和物流环节。",
                "5. 对高频问题补充说明文档、FAQ、短视频教程或客服标准回复。",
                "\n### 需要同步的角色",
                "- 客服\n- 商品\n- 运营\n- 仓配",
                "\n### 复盘记录字段",
                "- sku_id\n- 退款率\n- 退款订单数\n- 退款金额\n- TOP 退款原因\n- 处理责任人\n- 修复动作\n- 修复后退款率变化",
                "\n### 后续优化建议",
                "- 将退款原因结构化，形成商品质量和页面表达的反馈闭环。",
            ]
        )

    def add_fulfillment_sop() -> None:
        sections.extend(
            [
                "\n## 三、场景名称：延迟发货 / 履约异常",
                "\n### 触发条件",
                "- shipping_days > 3。",
                "- 订单状态为已付款，但履约状态长期为待发货。",
                "\n### 处理步骤",
                "1. 仓配团队核查订单是否卡在拣货、打包、出库或面单环节。",
                "2. 供应链确认是否因库存不足导致无法发货。",
                "3. 客服主动同步订单进度，降低用户投诉和退款风险。",
                "4. 运营评估是否需要暂停相关 SKU 的广告投放或活动承接。",
                "\n### 需要同步的角色",
                "- 仓配\n- 供应链\n- 客服\n- 运营",
                "\n### 复盘记录字段",
                "- order_id\n- sku_id\n- 下单日期\n- 发货耗时\n- 卡点环节\n- 客服触达状态\n- 是否退款\n- 最终处理结果",
                "\n### 后续优化建议",
                "- 建立“已付款但待发货超过 48 小时”的自动提醒机制。",
            ]
        )

    def add_overstock_sop() -> None:
        sections.extend(
            [
                "\n## 四、场景名称：滞销积压",
                "\n### 触发条件",
                "- 近 7 日日均销量低于 3 件。",
                "- 预计可售天数超过 60 天。",
                "\n### 处理步骤",
                "1. 商品团队复盘选品、定价、规格和用户反馈。",
                "2. 运营检查曝光、点击和转化链路，判断是流量不足还是转化不足。",
                "3. 销售团队设计组合销售、赠品、套装或替代推荐方案。",
                "4. 供应链评估是否需要调拨、清仓或停止补货。",
                "\n### 需要同步的角色",
                "- 商品\n- 运营\n- 销售\n- 供应链",
                "\n### 复盘记录字段",
                "- sku_id\n- 可售库存\n- 近 7 日日均销量\n- 库存周转天数\n- 价格调整动作\n- 促销动作\n- 清仓进度",
                "\n### 后续优化建议",
                "- 在新品上架 14 天后建立首轮转化与库存健康检查。",
            ]
        )

    risk_text = " ".join(inventory_risks.get("risk_reason", pd.Series(dtype=str)).astype(str).tolist()) if _df_has_rows(inventory_risks) else ""
    exception_types = set(order_exceptions.get("exception_type", pd.Series(dtype=str)).astype(str).tolist()) if _df_has_rows(order_exceptions) else set()

    if "热销缺货" in risk_text or "库存不足" in risk_text:
        add_hot_stockout_sop()
    if "滞销积压" in risk_text:
        add_overstock_sop()
    if any("退款异常" in item or "售后异常" in item for item in exception_types):
        add_refund_sop()
    if any("延迟发货" in item or "履约异常" in item for item in exception_types):
        add_fulfillment_sop()

    if len(sections) == 1:
        sections.append("\n当前未识别到明确异常场景，建议保留日常巡检 SOP：每日检查销售、库存、履约和售后四类指标。")

    return "\n".join(sections)


def generate_daily_report(results: dict[str, Any]) -> str:
    metrics = results.get("overall_metrics", {})
    sku_metrics = results.get("sku_metrics", pd.DataFrame())
    inventory_risks = results.get("inventory_risks", pd.DataFrame())
    order_exceptions = results.get("order_exceptions", pd.DataFrame())
    platform_metrics = results.get("platform_metrics", pd.DataFrame())
    channel_metrics = results.get("channel_metrics", pd.DataFrame())
    data = results.get("data", {})
    sales_daily = data.get("sales_daily", pd.DataFrame())

    if _df_has_rows(sales_daily) and "date" in sales_daily.columns:
        max_date = sales_daily["date"].max()
        report_date = max_date.strftime("%Y-%m-%d") if pd.notna(max_date) else datetime.today().strftime("%Y-%m-%d")
    else:
        report_date = datetime.today().strftime("%Y-%m-%d")

    findings = build_key_findings(results)
    feishu_notice = generate_feishu_notice(results)
    sop = generate_sop_suggestions(results)

    gmv_top = sku_metrics.sort_values("sku_gmv", ascending=False) if _df_has_rows(sku_metrics) and "sku_gmv" in sku_metrics.columns else pd.DataFrame()
    units_top = sku_metrics.sort_values("sku_units_sold", ascending=False) if _df_has_rows(sku_metrics) and "sku_units_sold" in sku_metrics.columns else pd.DataFrame()
    refund_top = sku_metrics[sku_metrics.get("sku_orders", 0) > 0].sort_values("sku_refund_rate", ascending=False) if _df_has_rows(sku_metrics) and "sku_refund_rate" in sku_metrics.columns else pd.DataFrame()

    low_roi = pd.DataFrame()
    if _df_has_rows(sku_metrics) and "sku_ad_roi" in sku_metrics.columns:
        low_roi = sku_metrics[(sku_metrics["sku_ad_spend"] > 0) & (sku_metrics["sku_ad_roi"] < 2)].sort_values("sku_ad_roi")

    report_parts = [
        f"# 电商运营日报｜{report_date}",
        "",
        "## 一、今日核心结论",
        *[f"- {item}" for item in findings],
        "",
        "## 二、销售表现总结",
        f"- 总 GMV：{format_currency(metrics.get('total_gmv', 0))}",
        f"- 总销量：{metrics.get('total_units', 0):,.0f} 件",
        f"- 总订单数：{metrics.get('total_orders', 0):,.0f} 单",
        f"- 平均客单价：{format_currency(metrics.get('avg_order_value', 0))}",
        f"- 平均转化率：{format_percent(metrics.get('avg_conversion_rate', 0))}",
        f"- 退款率：{format_percent(metrics.get('refund_rate', 0))}",
        f"- 广告 ROI：{metrics.get('ad_roi', 0):.2f}",
        "",
        "### 平台表现",
        _markdown_table(platform_metrics, ["platform", "gmv", "orders", "sessions", "conversion_rate", "ad_roi"], max_rows=10),
        "",
        "### 渠道表现",
        _markdown_table(channel_metrics, ["platform", "channel", "gmv", "orders", "units_sold", "conversion_rate"], max_rows=10),
        "",
        "## 三、重点 SKU 表现",
        "### GMV TOP 10 SKU",
        _markdown_table(gmv_top, ["sku_id", "product_name", "sku_gmv", "sku_units_sold", "sku_orders", "sku_ad_roi"], max_rows=10),
        "",
        "### 销量 TOP 10 SKU",
        _markdown_table(units_top, ["sku_id", "product_name", "sku_units_sold", "sku_gmv", "avg_daily_sales_7d", "stock_days"], max_rows=10),
        "",
        "### 退款率 TOP 10 SKU",
        _markdown_table(refund_top, ["sku_id", "product_name", "sku_orders", "sku_refunds", "sku_refund_rate"], max_rows=10),
        "",
        "## 四、库存风险预警",
        _markdown_table(
            inventory_risks,
            ["sku_id", "product_name", "available_stock", "safety_stock", "lead_time_days", "avg_daily_sales_7d", "stock_days", "risk_level", "risk_reason", "suggested_action"],
            max_rows=10,
        ),
        "",
        "## 五、订单异常分析",
        _markdown_table(
            order_exceptions,
            ["exception_type", "sku_id", "product_name", "exception_count", "risk_reason", "suggested_action"],
            max_rows=20,
        ),
        "",
        "## 六、可能原因分析",
    ]

    if _df_has_rows(inventory_risks):
        report_parts.append("- 库存风险主要来自热销 SKU 销量释放快于补货周期，或滞销 SKU 需求不足导致库存周转偏慢。")
    else:
        report_parts.append("- 当前库存数据未显示明确异常，仍建议保留安全库存与补货周期巡检。")

    if _df_has_rows(order_exceptions):
        report_parts.append("- 订单异常可能与仓配履约时效、退款原因集中、待付款转化链路或售后说明不足有关。")
    else:
        report_parts.append("- 当前订单数据未显示明显异常。")

    if _df_has_rows(low_roi):
        report_parts.append("- 部分 SKU 广告 ROI 低于 2，可能存在投放预算高、转化低或客单价承接不足的问题。")
    else:
        report_parts.append("- 当前未识别到明显低 ROI 投放 SKU。")

    report_parts.extend(
        [
            "",
            "## 七、建议动作",
            "### 运营",
            *[f"- {item}" for item in ROLE_ACTIONS["运营"]],
            "### 供应链",
            *[f"- {item}" for item in ROLE_ACTIONS["供应链"]],
            "### 客服",
            *[f"- {item}" for item in ROLE_ACTIONS["客服"]],
            "### 销售",
            *[f"- {item}" for item in ROLE_ACTIONS["销售"]],
            "### 商品",
            *[f"- {item}" for item in ROLE_ACTIONS["商品"]],
            "",
            "## 八、需要同步的团队",
        ]
    )

    sync_roles = ["运营", "供应链", "客服"]
    if _df_has_rows(order_exceptions):
        sync_roles.extend(["销售", "商品"])
    if _df_has_rows(inventory_risks):
        sync_roles.extend(["仓配"])
    sync_roles = list(dict.fromkeys(sync_roles))
    report_parts.append("- " + "、".join(sync_roles))

    report_parts.extend(
        [
            "",
            "## 九、飞书通知文案",
            feishu_notice,
            "",
            "## 十、SOP / 复盘沉淀建议",
            sop.replace("# SOP / 复盘沉淀建议", "").strip(),
            "",
            "---",
            "备注：当前版本为本地规则 + 模板版 Demo，未调用外部大模型 API。后续可将本模块替换为 OpenAI / DeepSeek / Kimi 等 OpenAI-compatible API。",
        ]
    )

    return "\n".join(str(part) for part in report_parts)
