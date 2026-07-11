---
name: company-distiller
description: "从公开披露、网站、CRM、访谈、合同、工单和产品使用数据中构建并持续更新受治理的公司对象，再按受众导出公司 Skill。适用于创建或刷新企业数字映射、客户知识、本体包、销售或客户成功视图、可追溯的企业分析，以及带来源链和策略过滤的版本化公司快照。"
---

# 公司蒸馏器

把公司维护为一个版本化的证据系统。将规范层的实体、结构化记录、事件、证据、主张和关系，与供 Agent 阅读的派生 Skill 严格分离。

## 必需模型

首次构建或增量更新前，阅读 `references/system-architecture.md`。始终区分三个领域：

- 公司本体：身份、业务单元、产品、能力、战略与风险；
- 商业关系：CRM、联系人、商机、访谈、合同与义务；
- 产品使用与服务：订阅、使用量、工单与健康信号。

不要把 CRM 阶段当作客户意向，不要把合同当作产品采纳，不要把单个工单当作公司级弱点，也不要把使用量当作满意度。

## 工作流程

1. 确认目标公司、法律与业务边界、数据源模式、用例、输出路径、受众和用途。使用 `prompts/intake.md`。
2. 创建新对象时运行：

   ```bash
   python3 scripts/scaffold_company_skill.py --name "Company Name" --slug company-slug --output ./company-object
   ```

   公司名称不含 ASCII 字符时，必须显式提供 ASCII `--slug`。
3. 盘点不可变的数据源版本。按 `references/data-routing.md` 和 `prompts/source_router.md` 路由每个数据源。
4. 将 CRM、访谈、合同、工单和使用数据保留为有类型的 `records`；再创建可寻址的 `evidence`、不可变的 `claims` 与 `relations`。严格遵循 `schemas/` 中的 JSON 契约。
5. 创建运行包：包含 `run.json`，以及 `example/evolving-company/bundles/` 所示的 JSONL 文件。写入摘要：

   ```bash
   python3 scripts/update_bundle_digest.py ./run-bundle
   ```

6. 完成全部预校验后应用运行包：

   ```bash
   python3 scripts/apply_run.py ./company-object ./run-bundle
   ```

   当前本地多文件实现不提供数据库事务或跨进程锁。不得修改已接纳的账本行；使用 `supersedes` 纠正旧主张，使用 `contradicts` 保留未解决的备选说法，使用撤回主张终止错误结论。
7. 校验规范工作区：

   ```bash
   python3 scripts/validate_company_object.py ./company-object
   ```

8. 按获授权的受众和用途分别导出 Skill：

   ```bash
   python3 scripts/export_company_skill.py ./company-object --audience sales --output ./sales-company-skill
   python3 scripts/validate_company_skill.py ./sales-company-skill
   ```

9. 发布前运行 `python3 scripts/run_acceptance.py`。将 `references/evaluation-rubric.md` 中的每一道门禁都视为强制要求。

## 抽取规则

- 使用 `prompts/company_analyzer.md` 生成公司领域的 Claim 候选。
- 使用 `prompts/financials_analyzer.md` 处理指标和会计口径。
- 仅对重复出现、具有解释力且边界明确的战略逻辑使用 `prompts/strategy_cognition_analyzer.md`。
- 使用 `prompts/evidence_merger.md` 决定生命周期和冲突处理方式。
- 分开记录业务有效时间与系统观察时间。
- 保留数据源定位符和哈希；不要把结构化输入压平成只有散文的证据。
- 导出前应用策略。提示词不是访问控制机制。

## 更新规则

- 要求运行包的 `base_snapshot_id` 与当前快照一致。
- 在写入文件系统前拒绝重复 ID、断裂引用、非法时间区间、过期基线和策略降级。
- 保留 `proposed` 和 `rejected` Claim 以便审计，但只发布 `accepted` Claim。
- 始终从快照重新生成受众 Skill；不得把 Markdown 当作规范存储。
- 数据源被纠正或撤回时，创建新运行，通过 `supersedes` 或撤回来处理受影响 Claim，并重新评估派生 Claim。

## 派生 Skill 的回答边界

派生 Skill 必须区分事实（`fact`）、观察（`observation`）、转述（`statement`）、推断（`inference`）、假设（`hypothesis`）、义务（`obligation`）和未解决冲突。对会变化的主张给出有效日期和观察日期。若问题所称的“最新”或“当前”晚于投影日期，应刷新规范对象，或明确说明投影已经过期（`stale`）。

没有直接且获授权的证据时，不得断言采购意向、产品采纳、满意度、安全态势、法律结果或投资结论。

## 资源

- `references/user-manual.md`：中文使用手册与完整命令流程。
- `references/high-level-design.md`：中文概要设计、模块边界与运行时序。
- `references/system-architecture.md`：对象边界、分层、运行、时间、治理和内部数据源契约。
- `references/company-ontology.md`：公司、商业关系和产品使用领域的本体词汇。
- `references/data-routing.md`：从数据源到记录、证据和 Claim 的路由规则。
- `references/evaluation-rubric.md`：可执行的发布门禁。
- `references/optimization-plan.md`：目标结果和实现阶段。
- `schemas/`：机器可读的规范层契约。
- `example/evolving-company/`：三次运行、四种受治理投影的当前示例。
