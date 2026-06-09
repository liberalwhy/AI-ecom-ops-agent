# Ecom Ops Agent｜电商 AI 运营流程分析助手

## 一、项目定位

Ecom Ops Agent 是一个电商 AI 运营流程分析助手，用于模拟电商运营中的数据导入、字段清洗、指标计算、异常识别、AI 总结、飞书通知和 SOP 沉淀流程。

这个 Demo 面向电商运营、商品运营、销售运营、供应链协同团队。用户可以上传或直接使用内置示例的 SKU 数据、销售数据、库存数据和订单数据，系统会自动输出接近真实业务交付格式的电商运营分析文档。

项目核心流程：

```text
数据导入 → 字段清洗 → 指标计算 → 异常识别 → AI 总结 → 人工确认 → 飞书通知 → SOP / 复盘沉淀
```

## 二、项目不是做什么

这个项目不是完整 ERP，不是真实电商后台，也不是复杂预测系统。

它不会直接连接天猫、京东、亚马逊、Shopify 或企业内部仓储系统；当前版本也不会真实调用大模型 API、飞书 API 或数据库。

## 三、项目真正展示什么

这个项目不是单纯做销售数据看板，也不是普通聊天式 AI 回答，而是把电商运营中的 SKU、销售、库存、订单、异常处理、飞书同步和 SOP 沉淀流程拆解成可复用、可培训、可交付的 AI 工作流 Demo。

它展示的是如何把电商运营流程拆解成：

- 数据字段
- 分析规则
- 异常判断
- AI 总结
- 飞书通知
- SOP 沉淀
- 人工确认节点
- 后续可扩展的智能体工作流

## 四、适用场景

- 电商运营日报
- SKU 表现分析
- 库存风险预警
- 订单异常排查
- 供应链协同
- 销售 / 客服同步
- SOP / 复盘沉淀
- AI Agent 作品集展示

## 五、本地运行方式

### 1. 进入项目目录

```bash
cd ecom-ops-agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

如果 `pip` 不可用，请使用：

```bash
python -m pip install -r requirements.txt
```

### 3. 启动 Streamlit

```bash
streamlit run app.py
```

如果 `streamlit` 命令不可用，请使用：

```bash
python -m streamlit run app.py
```

### 4. 打开浏览器

启动后，终端会显示本地访问地址，通常是：

```text
http://localhost:8501
```

## 六、项目文件结构

```text
ecom-ops-agent/
├── app.py
├── data_generator.py
├── data_processor.py
├── report_generator.py
├── requirements.txt
├── README.md
├── sample_input.md
└── sample_data/
    ├── sku_master.csv
    ├── sales_daily.csv
    ├── inventory_daily.csv
    └── orders.csv
```

## 七、字段说明

### 1. SKU 主数据表：`sample_data/sku_master.csv`

| 字段 | 说明 |
|---|---|
| sku_id | SKU 编码 |
| spu_id | 商品款 ID |
| product_name | 商品名称 |
| category | 商品类目 |
| variant | 规格 / 版本 |
| platform | 销售平台 |
| price | 售价 |
| listing_status | 上架状态 |
| launch_date | 上架日期 |
| product_owner | 商品负责人 |

### 2. 销售数据表：`sample_data/sales_daily.csv`

| 字段 | 说明 |
|---|---|
| date | 日期 |
| platform | 平台 |
| channel | 渠道 |
| sku_id | SKU 编码 |
| sessions | 访客数 |
| clicks | 点击数 |
| orders | 订单数 |
| units_sold | 销售件数 |
| gmv | 销售额 |
| refunds | 退款订单数 |
| refund_amount | 退款金额 |
| ad_spend | 广告花费 |

### 3. 库存数据表：`sample_data/inventory_daily.csv`

| 字段 | 说明 |
|---|---|
| date | 日期 |
| sku_id | SKU 编码 |
| warehouse | 仓库 |
| available_stock | 可售库存 |
| locked_stock | 锁定库存 |
| inbound_stock | 在途库存 |
| safety_stock | 安全库存 |
| lead_time_days | 补货周期 |
| stock_status | 库存状态 |

### 4. 订单数据表：`sample_data/orders.csv`

| 字段 | 说明 |
|---|---|
| order_id | 订单号 |
| order_date | 下单日期 |
| platform | 平台 |
| channel | 渠道 |
| sku_id | SKU 编码 |
| quantity | 购买数量 |
| paid_amount | 支付金额 |
| order_status | 订单状态 |
| fulfillment_status | 履约状态 |
| refund_status | 退款状态 |
| refund_amount | 退款金额 |
| shipping_days | 发货耗时 |
| customer_issue | 用户问题 |

## 八、核心指标计算逻辑

### 整体销售指标

- GMV = `gmv` 汇总
- 销量 = `units_sold` 汇总
- 订单数 = `orders` 汇总
- 客单价 = GMV / 订单数
- 转化率 = 订单数 / 访客数
- 退款率 = 退款订单数 / 订单数
- 广告 ROI = GMV / 广告花费

当分母为 0 时，系统返回 0，避免报错。

### SKU 指标

- SKU GMV
- SKU 销量
- SKU 订单数
- SKU 退款率
- SKU 近 7 日日均销量
- SKU 预计可售天数

预计可售天数 = 可售库存 / 近 7 日日均销量。如果近 7 日日均销量为 0，系统用 999 表示“暂无销量或无法判断”。

### 库存风险识别

系统会识别以下库存风险：

1. 高风险库存不足：可售库存 <= 安全库存，或预计可售天数 <= 补货周期。
2. 中风险库存不足：预计可售天数 <= 补货周期 + 3 天，或可售库存 <= 安全库存 × 1.5。
3. 热销缺货风险：SKU 是热销 SKU，同时预计可售天数低于补货周期 + 3 天。
4. 滞销积压：近 7 日日均销量低于 3 件，同时预计可售天数大于 60 天。

### 订单异常识别

系统会识别以下订单异常：

1. 延迟发货：`shipping_days > 3`。
2. 退款异常：SKU 退款率 > 5%。
3. 待付款异常：待付款订单占比 > 15%。
4. 履约异常：订单状态为已付款，但履约状态长期为待发货。
5. 售后异常：`customer_issue` 中集中出现“质量问题”“物流延迟”“缺件”“不会使用”等问题。

## 九、输出模块

Streamlit 页面包含以下模块：

1. 项目标题与说明
2. 数据导入区
3. 数据预览区
4. 核心指标看板
5. SKU 分析区
6. 库存风险区
7. 订单异常区
8. AI 运营日报生成区
9. 飞书通知文案区
10. SOP / 复盘沉淀建议区
11. Markdown 下载区

点击“生成 AI 运营日报”后，系统会生成：

- 电商运营日报 Markdown
- 飞书通知 Markdown
- SOP / 复盘沉淀建议 Markdown

## 十、Demo 价值

这个项目展示的是如何把电商运营流程拆解成数据字段、分析规则、异常判断、AI 总结、飞书通知和 SOP 沉淀，而不是单纯生成一段文案。

它适合用于求职作品集展示，重点体现：

- 对电商运营业务链路的理解
- 对 SKU、销售、库存、订单数据结构的抽象能力
- 用 Pandas 完成指标计算和异常识别的能力
- 把数据分析结果包装成真实业务交付文档的能力
- 把 AI Agent 放入业务流程，而不是只做聊天问答的产品思维

## 十一、当前版本说明

当前版本不调用任何大模型 API，也不需要配置 API Key。

`report_generator.py` 已经把报告生成逻辑独立出来，后续可以在这里替换成真实大模型调用，例如：

- OpenAI API
- DeepSeek API
- Kimi API
- 其他 OpenAI-compatible API

请不要把 API Key 写入代码。后续接入 API 时，建议使用：

- `.env` 环境变量
- Streamlit Secrets
- 企业内部密钥管理服务

## 十二、后续可扩展方向

- 接入 OpenAI / DeepSeek / Kimi 等大模型 API
- 接入飞书多维表格
- 接入飞书机器人通知
- 接入真实 Shopify / 亚马逊 / 天猫 / 京东数据
- 增加 SQL 查询功能
- 增加库存预测
- 增加 RAG 知识库
- 增加自动生成周报 / 月报 / 复盘报告
- 增加多角色协同看板
- 增加运营动作状态流转，例如“待确认、处理中、已完成、已复盘”
- 增加人工确认节点，将 AI 建议转化成可执行任务
- 增加异常规则配置页面，让运营负责人自定义阈值
