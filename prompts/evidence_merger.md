# 证据合并提示词

将 Claim 候选与当前快照比较，并提出不可变的生命周期决策。不得原地更新或删除已接纳的行。

## 决策

- `new`：已接纳 Claim 没有语义等价的当前断言。
- `reinforced`：新的已接纳 Claim 与旧 Claim 语义签名相同，但增加了新证据；新 Claim 成为当前版本。
- `superseded`：新的已接纳 Claim 替代指定的旧 Claim。
- `conflicted`：已接纳的备选说法通过 `contradicts` 相互指向；不得静默偏好其中一方。
- `retracted`：新的撤回 Claim 通过 `supersedes` 指向被撤回的 Claim。
- `unchanged`：`proposed`/`rejected` 内容，或没有可发布变化的输入。

## 规则

1. 比较主题、谓词、带类型的值、`scope` 和有效区间。
2. 不同会计口径、实体范围、产品、地区和时期应保留为不同 Claim，而不是判为冲突。
3. 只有在 Claim 指向同一断言时，才依据证据质量选择主证据。
4. 每一条生命周期记录都要保留证据和策略继承关系。
5. 支撑 Claim 被替代、冲突或撤回时，重新评估派生 Claim。
6. 返回可写入运行包的 JSON 候选行，由 `apply_run.py` 完成最终变更分类、完整预校验和追加写入。
