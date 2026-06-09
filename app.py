"""Streamlit app for Ecom Ops Agent."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from data_generator import generate_all
from data_processor import REQUIRED_COLUMNS, analyze_ecom_ops, format_currency, format_percent, read_csv_safely
from report_generator import generate_daily_report, generate_feishu_notice, generate_sop_suggestions


APP_TITLE = "Ecom Ops Agent｜电商 AI 运营流程分析助手"
BASE_DIR = Path(__file__).parent
SAMPLE_DIR = BASE_DIR / "sample_data"


st.set_page_config(
    page_title="Ecom Ops Agent",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def load_sample_data() -> dict[str, pd.DataFrame]:
    required_files = [
        SAMPLE_DIR / "sku_master.csv",
        SAMPLE_DIR / "sales_daily.csv",
        SAMPLE_DIR / "inventory_daily.csv",
        SAMPLE_DIR / "orders.csv",
    ]
    if not all(path.exists() for path in required_files):
        generate_all(SAMPLE_DIR)
    return {
        "sku_master": read_csv_safely(SAMPLE_DIR / "sku_master.csv"),
        "sales_daily": read_csv_safely(SAMPLE_DIR / "sales_daily.csv"),
        "inventory_daily": read_csv_safely(SAMPLE_DIR / "inventory_daily.csv"),
        "orders": read_csv_safely(SAMPLE_DIR / "orders.csv"),
    }


def _read_uploaded(uploaded_file, fallback_df: pd.DataFrame) -> pd.DataFrame:
    if uploaded_file is None:
        return fallback_df.copy()
    return read_csv_safely(uploaded_file)


def load_data_from_ui() -> tuple[dict[str, pd.DataFrame], str]:
    sample_data = load_sample_data()

    with st.sidebar:
        st.header("数据导入")
        st.caption("未上传文件时，系统自动使用内置示例数据。")
        sku_file = st.file_uploader("SKU 主数据表 sku_master.csv", type=["csv"])
        sales_file = st.file_uploader("销售数据表 sales_daily.csv", type=["csv"])
        inventory_file = st.file_uploader("库存数据表 inventory_daily.csv", type=["csv"])
        orders_file = st.file_uploader("订单数据表 orders.csv", type=["csv"])

        use_sample = all(file is None for file in [sku_file, sales_file, inventory_file, orders_file])
        data_mode = "内置示例数据" if use_sample else "上传数据 + 未上传表使用示例数据补齐"
        st.info(f"当前模式：{data_mode}")

    data = {
        "sku_master": _read_uploaded(sku_file, sample_data["sku_master"]),
        "sales_daily": _read_uploaded(sales_file, sample_data["sales_daily"]),
        "inventory_daily": _read_uploaded(inventory_file, sample_data["inventory_daily"]),
        "orders": _read_uploaded(orders_file, sample_data["orders"]),
    }
    return data, data_mode


def render_validation(validation) -> None:
    if not validation.has_issue:
        st.success("字段校验通过，sku_id 关联关系正常。")
        return

    if validation.missing_fields:
        st.warning("检测到字段缺失，请确认上传 CSV 是否符合字段要求。")
        for table, fields in validation.missing_fields.items():
            st.write(f"- `{table}` 缺失字段：{', '.join(fields)}")

    for warning in validation.relation_warnings:
        st.warning(warning)
    for warning in validation.duplicate_warnings:
        st.warning(warning)


def render_data_preview(data: dict[str, pd.DataFrame]) -> None:
    st.header("三、数据预览区")
    tabs = st.tabs(["SKU 主数据表", "销售数据表", "库存数据表", "订单数据表"])
    table_map = {
        "SKU 主数据表": "sku_master",
        "销售数据表": "sales_daily",
        "库存数据表": "inventory_daily",
        "订单数据表": "orders",
    }
    for tab, (label, key) in zip(tabs, table_map.items()):
        with tab:
            required = REQUIRED_COLUMNS[key]
            st.caption(f"字段要求：{', '.join(required)}")
            st.dataframe(data[key].head(10), use_container_width=True)


def render_metric_cards(metrics: dict) -> None:
    st.header("四、核心指标看板")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总 GMV", format_currency(metrics.get("total_gmv", 0)))
    col2.metric("总销量", f"{metrics.get('total_units', 0):,.0f} 件")
    col3.metric("总订单数", f"{metrics.get('total_orders', 0):,.0f} 单")
    col4.metric("平均客单价", format_currency(metrics.get("avg_order_value", 0)))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("平均转化率", format_percent(metrics.get("avg_conversion_rate", 0)))
    col6.metric("退款率", format_percent(metrics.get("refund_rate", 0)))
    col7.metric("库存风险 SKU 数", f"{metrics.get('inventory_risk_sku_count', 0)}")
    col8.metric("订单异常数", f"{metrics.get('order_exception_count', 0)}")


def render_sku_analysis(results: dict) -> None:
    st.header("五、SKU 分析区")
    sku_metrics = results["sku_metrics"].copy()
    inventory_risks = results["inventory_risks"].copy()

    if sku_metrics.empty:
        st.info("当前数据不足以展示 SKU 分析。")
        return

    tabs = st.tabs(["GMV TOP 10 SKU", "销量 TOP 10 SKU", "退款率 TOP 10 SKU", "库存风险 TOP 10 SKU"])
    with tabs[0]:
        st.dataframe(
            sku_metrics.sort_values("sku_gmv", ascending=False)[
                ["sku_id", "product_name", "platform", "sku_gmv", "sku_units_sold", "sku_orders", "sku_ad_roi"]
            ].head(10),
            use_container_width=True,
        )
    with tabs[1]:
        st.dataframe(
            sku_metrics.sort_values("sku_units_sold", ascending=False)[
                ["sku_id", "product_name", "platform", "sku_units_sold", "sku_gmv", "avg_daily_sales_7d", "stock_days"]
            ].head(10),
            use_container_width=True,
        )
    with tabs[2]:
        refund_df = sku_metrics[sku_metrics["sku_orders"] > 0].sort_values("sku_refund_rate", ascending=False)
        st.dataframe(
            refund_df[["sku_id", "product_name", "sku_orders", "sku_refunds", "sku_refund_rate", "sku_refund_amount"]].head(10),
            use_container_width=True,
        )
    with tabs[3]:
        if inventory_risks.empty:
            st.info("未识别到库存风险 SKU。")
        else:
            st.dataframe(inventory_risks.head(10), use_container_width=True)

    chart_df = sku_metrics.sort_values("sku_gmv", ascending=False).head(10).set_index("product_name")[["sku_gmv"]]
    st.subheader("GMV TOP 10 可视化")
    st.bar_chart(chart_df)


def render_inventory_risk(results: dict) -> None:
    st.header("六、库存风险区")
    inventory_risks = results["inventory_risks"]
    if inventory_risks.empty:
        st.success("当前未识别到明确库存风险。")
        return
    show_cols = [
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
    st.dataframe(inventory_risks[show_cols], use_container_width=True)


def render_order_exceptions(results: dict) -> None:
    st.header("七、订单异常区")
    order_exceptions = results["order_exceptions"]
    if order_exceptions.empty:
        st.success("当前未识别到明显订单异常。")
        return
    show_cols = ["exception_type", "sku_id", "product_name", "exception_count", "risk_reason", "suggested_action"]
    st.dataframe(order_exceptions[show_cols], use_container_width=True)


def render_report_area(results: dict) -> None:
    st.header("八、AI 运营日报生成区")
    st.caption("当前版本为本地规则 + 模板版 Demo，不调用任何大模型 API。报告生成模块已预留后续接入 OpenAI / DeepSeek / Kimi 等 API 的位置。")

    if "daily_report_md" not in st.session_state:
        st.session_state.daily_report_md = ""
        st.session_state.feishu_notice_md = ""
        st.session_state.sop_md = ""

    if st.button("生成 AI 运营日报", type="primary"):
        st.session_state.daily_report_md = generate_daily_report(results)
        st.session_state.feishu_notice_md = generate_feishu_notice(results)
        st.session_state.sop_md = generate_sop_suggestions(results)

    if st.session_state.daily_report_md:
        st.markdown(st.session_state.daily_report_md)
    else:
        st.info("点击按钮后生成 Markdown 运营日报。")

    st.header("九、飞书通知文案区")
    if st.session_state.feishu_notice_md:
        st.code(st.session_state.feishu_notice_md, language="markdown")
    else:
        st.info("生成日报后将自动生成适合飞书群同步的简短通知。")

    st.header("十、SOP / 复盘沉淀建议区")
    if st.session_state.sop_md:
        st.markdown(st.session_state.sop_md)
    else:
        st.info("生成日报后将自动生成 SOP / 复盘沉淀建议。")

    st.header("十一、Markdown 下载区")
    col1, col2, col3 = st.columns(3)
    col1.download_button(
        label="下载电商运营日报 Markdown",
        data=st.session_state.daily_report_md or generate_daily_report(results),
        file_name="ecom_ops_daily_report.md",
        mime="text/markdown",
        use_container_width=True,
    )
    col2.download_button(
        label="下载飞书通知 Markdown",
        data=st.session_state.feishu_notice_md or generate_feishu_notice(results),
        file_name="feishu_notice.md",
        mime="text/markdown",
        use_container_width=True,
    )
    col3.download_button(
        label="下载 SOP 建议 Markdown",
        data=st.session_state.sop_md or generate_sop_suggestions(results),
        file_name="sop_suggestions.md",
        mime="text/markdown",
        use_container_width=True,
    )


def main() -> None:
    st.title(APP_TITLE)
    st.write(
        "本工具用于模拟电商运营中的 AI 自动化分析流程。用户可以上传 SKU、销售、库存和订单数据，"
        "系统会自动完成指标计算、异常识别，并生成运营日报、库存预警、订单异常分析、补货建议、飞书通知文案和 SOP / 复盘沉淀建议。"
    )

    st.header("二、数据导入区")
    st.write("请在左侧上传 CSV 文件；如果不上传，系统默认使用 `sample_data/` 中的示例数据。")

    data, data_mode = load_data_from_ui()
    st.caption(f"当前数据模式：{data_mode}")

    results = analyze_ecom_ops(
        data["sku_master"],
        data["sales_daily"],
        data["inventory_daily"],
        data["orders"],
    )

    render_validation(results["validation"])
    render_data_preview(results["data"])
    render_metric_cards(results["overall_metrics"])
    render_sku_analysis(results)
    render_inventory_risk(results)
    render_order_exceptions(results)
    render_report_area(results)


if __name__ == "__main__":
    main()
