# Company Distiller 使用手册

## 1. 用途与适用对象

Company Distiller 把一家企业维护为可重复运行、可追溯、可按权限交付的“公司对象”。它接收公开资料以及 CRM、访谈、合同、工单、产品使用数据，保留结构化原始语义，生成带证据、时间、冲突和生命周期的 Claim，最后按受众导出只读 Company Skill。

本手册面向准备数据、执行蒸馏、审核结果和发布投影的工程、数据或知识运营人员。当前实现是本地参考实现，不自带生产连接器、任务调度、身份认证、加密存储或法务级保留策略。

## 2. 核心概念

| 概念 | 含义 |
|---|---|
| 规范工作区（canonical workspace） | 企业知识的唯一规范存储；包含追加式账本、策略、运行记录和快照 |
| run bundle | 一次初始或增量蒸馏的不可变输入包；包含 `run.json` 和若干 JSONL 集合 |
| Claim | 带主体、谓词、值、类型、时间、证据、审核决策、置信度、策略和生命周期链接的不可变断言 |
| snapshot | 一次成功 run 产生的当前状态物化；列出有效、冲突、撤回的 Claim 和有效关系 |
| change | 当前 run 对每个新 Claim 的变更分类：`new`、`reinforced`、`superseded`、`conflicted`、`retracted` 或 `unchanged` |
| projection | 从指定 snapshot 按 `audience` 和 `purpose` 白名单导出的只读交付视图 |
| provenance closure | 从 Claim/关系到 evidence，再到 source、record、event 和 run 的引用全部可解析，且派生证据无环 |

三个业务域必须分开建模：

- `company`：公司、法人、业务单元、产品、能力、战略和风险；
- `commercial_relationship`：账户、联系人/角色、商机、访谈、合同和义务；
- `product_use_service`：订阅、授权、使用观测、工单、事件和健康信号。

不要把 CRM 阶段当作客户采购意愿，不要把合同当作产品采用，不要把单个工单扩大为全公司缺陷，也不要把使用量等同于满意度或业务价值。

## 3. 前置条件

- Python 3，项目脚本只依赖当前仓库和 Python 标准库；
- 在项目根目录执行命令，或使用脚本和数据目录的绝对路径；
- 输入时间使用带时区的 ISO 8601 字符串，例如 `2026-07-11T09:30:00+08:00`；
- 所有 ID 在整个工作区内保持唯一、稳定，建议采用 `type:stable-key`；
- 先阅读 `schemas/` 中的 JSON Schema。机器契约与本文冲突时，以 Schema 和校验器为准。

## 4. 快速开始

以下示例创建一个中文名称的公司对象，应用首个 bundle，再导出销售投影：

```bash
python3 scripts/scaffold_company_skill.py \
  --name "示例科技有限公司" \
  --slug example-tech \
  --output ./work/example-tech

# 准备 ./bundles/run-001，具体结构见下一节
python3 scripts/update_bundle_digest.py ./bundles/run-001
python3 scripts/apply_run.py ./work/example-tech ./bundles/run-001
python3 scripts/validate_company_object.py ./work/example-tech

python3 scripts/export_company_skill.py ./work/example-tech \
  --audience sales \
  --output ./dist/example-tech-sales
python3 scripts/validate_company_skill.py ./dist/example-tech-sales
```

公司名称不含可用 ASCII 字母或数字时，必须显式提供 ASCII `--slug`。初始化命令只创建空账本；在首个有效 bundle 应用前，严格工作区校验会因关键集合为空而失败，这是预期行为。

## 5. 初始化规范工作区

```bash
python3 scripts/scaffold_company_skill.py \
  --name "Company Name" \
  --slug company-slug \
  --output ./company-object \
  --date 2026-07-11
```

可选参数：

- `--slug`：稳定 ASCII 标识；中文公司名必须提供；
- `--date`：工作区创建日期，默认当天；
- `--force`：删除并重建已存在的输出目录。此操作会丢失该目录中的全部内容，只能用于明确可重建的路径。

初始化会创建 `manifest.json`、默认治理策略、空 JSONL 账本和 `evals/test-prompts.json`。不要把 `scaffold_company_skill.py` 的历史命令名理解为直接创建交付 Skill；交付 Skill 只能从已接受的 snapshot 导出。

## 6. 准备 run bundle

推荐每次运行创建独立目录：

```text
run-001/
  run.json
  entities.jsonl
  sources.jsonl
  records.jsonl
  events.jsonl
  evidence.jsonl
  claims.jsonl
  relations.jsonl
```

JSONL 文件每行是一个 JSON 对象，可以为空。官方示例保留全部文件，便于审计和确定性重放。字段约束分别见 `schemas/entity.schema.json`、`source.schema.json`、`record.schema.json`、`event.schema.json`、`evidence.schema.json`、`claim.schema.json` 和 `relation.schema.json`。

`run.json` 至少要满足以下语义：

```json
{
  "id": "run:example-tech:001",
  "company_id": "company:example-tech",
  "base_snapshot_id": null,
  "started_at": "2026-07-11T01:00:00+00:00",
  "completed_at": "2026-07-11T01:05:00+00:00",
  "mode": "initial",
  "model": "your-model-version",
  "prompt_version": "company-distiller-v2",
  "input_digest": "",
  "connector_cursors": {},
  "status": "completed",
  "result_snapshot_id": "snapshot:example-tech:001"
}
```

首个 run 使用 `mode: "initial"` 和 `base_snapshot_id: null`。增量 run 使用 `mode: "incremental"`，并把 `base_snapshot_id` 精确设置为 `manifest.json` 中当前的 `current_snapshot_id`。所有 bundle 行的 `created_by_run` 必须等于本次 `run.id`。

### 6.1 数据路由顺序

对每份输入依次完成：

1. 创建不可变 `source` 版本，记录外部 ID、版本、哈希、定位符、来源日期、观察时间和策略；
2. 解析稳定 `entity`，避免把公司、法人、账户、角色、产品和订阅混为一体；
3. 将上游行保留为有类型的 `record`，将发生过的变化保留为 `event`；
4. 创建粒度最小且可定位的 `evidence`；
5. 创建原子 Claim 和有证据的 `relation`；
6. 对比当前 snapshot，设置 `supersedes` 或 `contradicts`，并继承访问策略。

CRM、访谈、合同、工单和产品使用记录的 `data` 有必需语义字段，详见 `references/system-architecture.md`。高频遥测不应逐行写入公司对象，应在分析存储中聚合后写入带指标定义、时间窗、维度、单位和质量说明的 `product_usage`。

### 6.2 时间与审核字段

- `valid_from` / `valid_to`：断言在业务世界中的有效期；
- `occurred_at`：事件实际发生时间；
- `observed_at`：来源系统或人员观察到它的时间；
- run 的 `completed_at`：该批数据进入系统的时间上界；
- `decision`：`proposed`、`accepted`、`rejected` 或 `retracted`；
- `claim_type`：保留 `fact`、`metric`、`statement`、`observation`、`inference`、`hypothesis`、`risk`、`obligation`、`unknown` 的认识论差异。

只有 `accepted` Claim 可进入当前或冲突集合；`retracted` 表示撤回，并且必须通过 `supersedes` 指向被撤回 Claim。不要修改已接受的历史行。

## 7. 计算输入摘要

完成 bundle 后执行：

```bash
python3 scripts/update_bundle_digest.py ./bundles/run-001
```

命令会按规范化 JSON 内容计算确定性 SHA-256，并回写 `run.json` 的 `input_digest`。任何 bundle 内容或 `run.json` 字段发生变化后，都必须重新执行。摘要不匹配时，run 会被拒绝。

## 8. 应用与校验

```bash
python3 scripts/apply_run.py ./company-object ./bundles/run-001
python3 scripts/validate_company_object.py ./company-object
```

应用前会检查 Schema、摘要、`created_by_run`、公司 ID、当前基线、全局重复 ID、引用、时间顺序、策略继承和 Claim 生命周期。校验通过后，数据追加到规范账本，并生成 `runs`、`changes`、`snapshots` 记录与新的 `current_snapshot_id`。

应用同一个 run、使用旧 `base_snapshot_id`，或提交语义相同但未显式 `supersedes` 的 Claim，都会被拒绝。拒绝发生在正常写入前；但当前本地多文件实现不具备数据库事务的崩溃恢复能力，生产环境不要把它视为强事务存储。

## 9. 重复运行与蒸馏语义

每轮只追加新行，并根据新 Claim 的字段生成变更类型：

| 输入方式 | `change_type` | snapshot 结果 |
|---|---|---|
| 无生命周期链接，且不存在相同语义 | `new` | 新 Claim 进入有效集合 |
| `supersedes` 指向语义完全相同的旧 Claim | `reinforced` | 旧 Claim 退出，新 Claim 进入有效集合 |
| `supersedes` 指向语义不同的旧 Claim | `superseded` | 旧 Claim 退出，新 Claim 进入有效集合 |
| `contradicts` 指向未解决的替代 Claim | `conflicted` | 双方从有效集合转入冲突集合 |
| `decision: "retracted"` 且 `supersedes` 旧 Claim | `retracted` | 旧 Claim 退出，撤回 Claim 进入撤回集合 |
| `decision` 为 `proposed` 或 `rejected` | `unchanged` | 保留审计记录，不进入当前 snapshot |

增量运行建议流程：读取 `current_snapshot_id`，用新来源版本和连接器游标生成 bundle，审核 Claim 决策，重新计算 digest，应用，校验，查看 `changes/index.jsonl`，最后重新导出受影响的投影。来源更正或撤回时，还要重新评估依赖它的派生 Claim。

## 10. 导出受控 Company Skill

支持四种受众及默认用途：

| `audience` | 默认 `purpose` | 典型用途 |
|---|---|---|
| `public` | `research` | 公开研究 |
| `sales` | `account-planning` | 销售账户规划 |
| `customer-success` | `customer-success` | 客户成功与服务 |
| `executive` | `executive-review` | 管理层复盘 |

```bash
python3 scripts/export_company_skill.py ./company-object \
  --audience customer-success \
  --output ./dist/customer-success

python3 scripts/validate_company_skill.py ./dist/customer-success
```

可用参数：`--purpose` 覆盖默认用途，`--snapshot` 导出历史 snapshot，`--force` 删除并重建已有输出目录。自定义 purpose 必须被所涉及策略的 `allowed_purposes` 允许。

投影包含授权的实体、Claim、历史生命周期、证据、关系、来源元数据和安全的 record/event/run provenance stub；不会复制规范 `records/records.jsonl` 或 `events/events.jsonl` 的原始 `data`、主体列表和连接器游标。不允许导出的来源定位符会被遮蔽。导出后必须运行 `validate_company_skill.py`，不要手工修改投影作为事实源；需要更正时应创建新 run，再重新导出。

## 11. 示例与验收

重建三轮示例及四种受众投影：

```bash
python3 scripts/build_evolving_example.py \
  --output ./example/evolving-company \
  --force
```

`--force` 会删除目标目录后重建，只能指向可再生示例目录。示例依次演示公开资料、CRM/访谈、合同/工单/使用数据，并覆盖冲突、更正、撤回和策略隔离。

运行全部发布门禁：

```bash
python3 scripts/run_acceptance.py
```

默认报告写入 `example/evolving-company/acceptance-report.json`。16 项门禁覆盖 Skill 包、Schema、内部数据保真、provenance closure、实体边界、时间完整性、增量基线、不可变历史、六类变更、确定性重放、策略继承、投影隔离、四个固定测试哨兵、严格校验、运行时回答边界和回归测试。全部通过才可视为参考实现验收通过；这不等于生产安全、通用秘密/PII 扫描、真实答案准确率或法务合规已获认证。

## 12. 常见故障

| 现象 | 常见原因 | 处理方式 |
|---|---|---|
| 非 ASCII 名称无法生成 slug | 未提供稳定 ASCII `--slug` | 显式传入 `--slug company-slug` |
| `input_digest` 不匹配 | 计算摘要后又改了文件 | 最后一步重新运行 `update_bundle_digest.py` |
| `base_snapshot_id` 过期 | 另一轮运行已更新当前 snapshot | 读取最新 manifest，基于新 snapshot 重新比较和生成 bundle |
| duplicate id | ID 已存在于任一规范集合，或 bundle 内重复 | 生成新的稳定 ID；不要复用历史 ID |
| unresolved reference | 被引用的实体、来源、证据、run 或 Claim 不存在 | 将依赖行纳入更早 run 或本次 bundle，并检查拼写 |
| policy less restrictive | 派生对象比依赖证据更公开或允许更多用途 | 提高分类等级，并收紧 audience/purpose 至依赖策略交集 |
| 时间区间非法 | 缺少时区、开始晚于结束，或观察晚于入库完成 | 修正为带时区时间，并核对业务时间与系统时间 |
| semantic duplicate | 新 Claim 与当前 Claim 语义相同但未声明关系 | 用 `supersedes` 明确表示强化 |
| 导出结果比预期少 | audience/purpose、主体策略或证据策略不允许 | 检查完整依赖链的策略；不要通过降低下游策略绕过 |
| 严格校验提示集合为空 | 只完成了初始化 | 先准备并应用首个有效 run |

## 13. 安全与运维边界

- `governance/policies.json` 控制语义校验和投影选择，但不能阻止操作系统用户直接读取本地文件；
- 默认目录未加密、无租户隔离、无身份认证，也不会自动执行 `retention_days` 删除；
- 个人标识应在进入 bundle 前令牌化，原始访谈、合同、工单和遥测应留在受控源系统；
- 不要把敏感原文写入公开策略的 `excerpt`、标题、ID 或其他可导出字段；
- 当前并发控制依赖 `base_snapshot_id`，没有跨进程文件锁；生产环境应使用带事务、唯一约束和乐观锁的持久化存储；
- 备份应覆盖完整规范工作区，而不是只备份 Markdown 投影。
