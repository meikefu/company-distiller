---
name: example-company-sales-company-skill
description: "面向 sales 受众、用途为 account-planning 的 Example Company (Synthetic) 受治理公司对象 Skill。用于回答有证据支持的公司问题，开展商业关系、产品使用、风险和客户规划分析，并识别过期数据。"
---

# Example Company (Synthetic) 公司 Skill

这是快照 `snapshot:example-company:003` 面向 `sales` 受众、服务于 `account-planning` 用途的只读投影。
规范层的原始记录和事件不包含在本交付包中。

## 证据日期

- 快照创建时间：`2026-07-01T01:00:00+00:00`
- 最新纳入的观察时间：`2026-07-01T01:00:00+00:00`
- 受众：`sales`
- 用途：`account-planning`

如果“最新”或“当前”问题晚于已纳入的观察时间，应刷新规范公司对象，或明确说明该投影已经过期（`stale`）。

## 回答协议

1. 只加载 `facts/` 中与问题相关的文件，再把重要表述解析到 `claims/index.jsonl` 和 `evidence/index.jsonl`。
2. 按 `claim_type` 和 `decision` 将输出标记为事实（`fact`）、观察（`observation`）、有证据支持的推断（`inference`）、假设或未解决冲突。
3. 对财务、合同、产品用量（usage）、客服、法律、市场和当前状态主张给出有效日期与观察日期。
4. 将 CRM 阶段视为卖方观察，将访谈内容视为有归属的陈述，将合同视为义务，将工单视为边界明确的事件，将用量指标视为限定时间窗内的观察。
5. 不得从单一记录类型推断采购意向、产品采纳、满意度或公司级弱点。
6. 对 `facts/conflicts.md` 中的主张展示冲突双方。
7. 不得尝试访问本投影排除的数据。

## 交付包目录

- `projection.json`：快照、受众、用途和纳入的 ID。
- `object/entities.jsonl`：获授权的实体身份。
- `facts/company.md`：公司本体领域 Claim。
- `facts/commercial-relationship.md`：获授权的 CRM、访谈和合同 Claim。
- `facts/product-use-service.md`：获授权的产品用量与客服 Claim。
- `facts/timeline.md`：业务有效时间与观察时间线。
- `facts/conflicts.md`：未解决的备选说法。
- `facts/retractions.md`：获授权的历史 Claim 撤回记录。
- `claims/index.jsonl`：投影中的当前规范 Claim。
- `claims/history.jsonl`：获授权的生命周期前序 Claim，不属于当前事实。
- `evidence/index.jsonl`：包含安全来源链的投影证据。
- `provenance/records.jsonl`：不含原始 `data` 或主体的记录元数据。
- `provenance/events.jsonl`：不含原始 `data` 或主体的事件元数据。
- `provenance/runs.jsonl`：模型、提示词、摘要与快照审计概要。
- `sources/index.jsonl`：带治理定位符的数据源版本。
- `relations/relations.jsonl`：投影中的有类型关系。
