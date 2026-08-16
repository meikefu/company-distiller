# 比亚迪公开来源路由

| 数据源 ID | 数据源类型 | 外部 ID/版本 | 业务日期 | 观察时间 | 记录类型 | 目标领域 | 策略 ID | 备注 |
|---|---|---|---|---|---|---|---|---|
| `source:byd-2025-annual-report` | `annual_report` | `HKEX:2026032703008` | 2025 财年，2026-03-27 发布 | 2026-08-16 | `public_fact` | `company` | `policy:public` | 经审计财务基线、业务与分部边界 |
| `source:byd-about-20260816` | `official_website` | `BYD-WEB:about-byd` | 2026-08-16 页面快照 | 2026-08-16 | `public_fact` | `company` | `policy:public` | 官网技术与上市信息；哈希锁定页面版本 |
| `source:byd-2026-07-production-sales` | `regulatory` | `HKEX:2026080200027` | 2026-07，2026-08-02 发布 | 2026-08-16 | `public_fact` | `company` | `policy:public` | 未经审计的月度/累计产销数据，可能调整 |

原始文件保存在 `raw/`，`content_hash` 对文件字节计算。证据使用 PDF 页码或官网页面区块作为定位符。
