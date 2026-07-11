# 系统架构

## 内容

1. 对象边界
2. 规范数据层
3. 增量运行协议
4. 时间与冲突语义
5. 治理与投影
6. 内部来源契约

## 对象边界

不得把每条内部记录都提升为目标公司的属性。系统维护三个相互连接的领域：

| 领域 | 对象 | 示例 |
|---|---|---|
| 公司 | `company`、`legal_entity`、`business_unit`、`site`、`product`，以及能力与战略 | `company:acme`、`unit:acme-security` |
| 商业关系 | `account`、`person`、`role`、`opportunity`、`contract`，以及义务与互动 | CRM 阶段历史、续约条款 |
| 产品使用与服务 | `subscription`、`product`、`ticket`、`metric`，以及权益、使用观察、事故与健康度信号 | 周活跃用户、严重程度为 1 的工单 |

CRM 阶段是销售方对商机的观察，不是客户意图的证明。访谈陈述属于特定发言人和时间。合同证明义务，不证明采用。工单是事故记录，不能自动推导为公司范围的产品缺陷。使用数据证明的是在特定指标定义下观察到的行为，不代表满意度或业务价值。

## 规范数据层

```text
company-object/
  manifest.json
  object/entities.jsonl
  sources/sources.jsonl
  records/records.jsonl
  events/events.jsonl
  evidence/index.jsonl
  claims/claims.jsonl
  relations/relations.jsonl
  governance/policies.json
  runs/runs.jsonl
  snapshots/index.jsonl
  changes/index.jsonl
  evals/test-prompts.json
```

- `sources`：不可变的上游材料版本，包含连接器、外部 ID、内容哈希、定位信息、时间戳和治理策略。
- `records`：类型化、规范化的 CRM、访谈、合同、工单和使用数据行。
- `events`：实际发生的事项，例如商机阶段变化、合同签署、续约、工单状态变化和使用异常。
- `evidence`：供断言引用、可精确定位的摘录或结构化观察。
- `claims`：包含范围、溯源、时间、审核决定、置信度维度和生命周期链接的类型化陈述。
- `relations`：稳定实体之间、由证据支撑的边。
- `runs`：仅追加的执行账本，记录基准快照、输入摘要、模型、提示词版本和来源游标。
- `snapshots`：不可变的当前状态物化结果。
- `changes`：每轮运行产生的 `new`、`reinforced`、`superseded`、`conflicted`、`retracted` 和 `unchanged` 结果。

Markdown 事实和生成的 Skill 都是投影。它们可以从获授权的快照重新生成，绝不能成为某项事实的唯一副本。

## 增量运行协议

1. 只初始化一次公司对象。
2. 准备包含 `run.json` 以及零个或多个类型化 JSONL 账本的运行包。
3. 要求 `base_snapshot_id` 等于当前快照，防止过期任务静默覆盖较新的知识。
4. 写入前验证 schema、ID、引用、时间字段、策略继承和断言生命周期链接。
5. 追加已接受的数据行，不重写任何早期账本行。
6. 对断言变更分类，并创建新的不可变快照。
7. 记录运行包摘要、提示词版本、模型和连接器游标。
8. 从新快照导出一个或多个面向特定受众的 Skill。

在干净工作区按相同顺序应用同一组运行包，必须生成相同的快照内容哈希。因预校验被拒绝的运行不得改变任何账本；进程在多文件写入期间崩溃时，当前本地实现不保证事务回滚。

## 时间与冲突语义

系统同时使用业务时间和系统时间：

- `valid_from` / `valid_to`：断言在所建模现实中成立的时间范围；
- `occurred_at`：事件实际发生时间；
- `observed_at`：来源系统或人员观察到该事项的时间；
- 摄取时间：断言的 `created_by_run` 所指运行的 `completed_at`；
- `source_date`：来源发布或形成日期。

断言是不可变陈述。后续已接受断言可在 `supersedes` 中列出被替代的断言 ID。撤回通过一条 `decision` 为 `retracted` 的新断言表示，并且必须替代至少一条早期断言。未解决的互斥观点使用 `contradicts`，作为冲突持续可见，不能静默合并。`proposed` 和 `rejected` 断言为审计保留，但不发布到快照。

置信度是多维的，包括来源可靠性、交叉印证、推断强度和有边界的综合等级。置信度不能替代审核决定或访问策略。

## 治理与投影

策略定义数据分类、允许受众、用途、留存和个人数据处理方式。支持的受众为：

- `public`
- `sales`
- `customer-success`
- `executive`

证据单元的限制程度不得低于它引用的任何对象。断言或关系的限制程度不得低于其所有支持证据；其允许受众必须是每项支持策略允许受众的子集。验证器负责执行这项继承规则。

导出采用允许列表策略。生成的 Skill 只包含获授权的实体、断言、证据、来源元数据、安全的记录或事件溯源摘要、运行摘要和关系。溯源摘要会移除原始 `data`、主体列表和连接器游标。投影不得包含规范记录或事件载荷、原始访谈、原始合同、原始工单或原始使用数据。标记为非公开的来源定位信息保留在规范工作区，并从公开投影中移除。

## 内部来源契约

| `record_type` | `data` 中必需的语义字段 |
|---|---|
| `crm_account` | 上游客户 ID、负责人或团队、生命周期状态 |
| `crm_contact` | 上游联系人 ID、角色、客户链接；个人标识符应尽可能令牌化 |
| `crm_opportunity` | 阶段、存在时的金额与币种、关闭日期、购买背景 |
| `crm_activity` | 活动类型、以实体 ID 表示的参与者、结果 |
| `interview_segment` | 访谈 ID、发言实体或角色、问题或主题、逐字稿定位信息、同意范围 |
| `contract_term` | 签约实体、合同或版本 ID、生效日期、产品、义务或条款，以及适用时的币种和金额 |
| `support_ticket` | 产品或版本、严重程度、状态、开启与关闭时间、已验证时的根因 |
| `product_usage` | 指标 ID 与定义、时间窗口、维度、数值、单位、样本或数据质量说明 |

连接器可以增加字段，但不得丢失上述语义。高频遥测继续存放在分析系统中；公司对象只接收带指标定义和时间窗口的有限聚合与异常信息。
