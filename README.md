# Company Distiller（公司蒸馏器）

Company Distiller 把公开资料、CRM、访谈、合同、工单和产品使用数据组织为可重复运行、可追溯、可按受众投影的版本化公司对象。它提供数据契约、增量运行协议、证据与 Claim 生命周期、策略过滤、投影导出和可执行验收。

## 适用范围

本仓库是本地参考实现和语义内核，不是生产级数据安全或合规系统。它不提供数据库事务、跨进程锁、身份认证、文件访问控制、静态加密、租户隔离，也不会自动执行数据保留或删除要求。

规范公司对象与交付 Skill 分离：JSON/JSONL 账本和快照是事实源，Markdown 与受众 Skill 是可重建投影。

## 示例数据声明

`example/evolving-company/` 中只使用 `Example Company (Synthetic)`、`Example Product` 和保留域名 `example.invalid`。相关 CRM、访谈、合同、工单、使用量、金额和事件均为纯合成测试夹具，不映射任何现实公司、产品或个人。

示例中的 `TEST_ONLY_*_SENTINEL_*` 字符串是固定的投影隔离测试标记，不是密码、令牌或真实业务秘密。公开网址使用保留的 `example.invalid` 域名，数据源连接器标记为 `fixture`。

本项目与任何现实公司、商标权利人或数据提供方不存在关联、授权、背书或代理关系。生成结果不构成法律、投资、采购、网络安全或合规意见。

仓库只承载通用蒸馏器实现和明确标记的合成夹具。不得提交真实公司的名称、商标、证券代码、网址、报告、财务或经营指标，也不得提交真实 CRM、访谈、合同、工单、遥测、个人信息或其他客户材料。真实数据只能在仓库外的受控环境中处理，并应使用匿名化标识和独立访问控制。

## 快速开始

下面的命令假设当前目录是本项目的 `company-distiller/` 目录。脚本不会自动抓取网页、读取 PDF 或替你生成事实；它只校验并应用已经整理好的运行包。

### 0. 前置依赖和目录

- Python 3.10 或更高版本；核心建模、应用、校验和导出脚本只依赖 Python 标准库，不需要 `pip install`。
- 下文命令使用 Bash/Zsh 语法；PowerShell 用户需要改写第 4 步读取快照的变量赋值。
- 在仓库根目录执行 `cd company-distiller`，再使用下文的相对路径。
- 完整 `run_acceptance.py` 的 G01 还要求 Codex 的 `skill-creator` 快速校验器位于 `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py`。普通 Python 环境没有该文件时，可以先运行单元测试和第 6 步合成示例；核心流水线仍可使用。
- 在 Codex 环境中首次使用时，运行回归测试和参考实现验收，确认本地环境正常：

```bash
cd /path/to/repository/company-distiller
python3 --version
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/run_acceptance.py --report ./reports/acceptance-report.json
```

`run_acceptance.py` 使用的是仓库内合成示例，不会写入你的公司对象。

### 1. 初始化规范公司对象

先创建空的规范账本。中文公司名必须显式提供 ASCII `--slug`；不要把这里的输出目录直接当成交付 Skill。

```bash
python3 scripts/scaffold_company_skill.py \
  --name "示例科技有限公司" \
  --slug example-tech \
  --output ./work/example-tech
```

初始化后，`work/example-tech/manifest.json` 的 `current_snapshot_id` 应为 `null`。这时还不能运行 `validate_company_object.py`，因为账本仍为空，这是预期行为。

### 2. 创建并填写首个运行包

`update_bundle_digest.py` 需要先看到完整的 `run.json` 和 7 个 JSONL 文件。用脚手架创建正确的文件名，再把已路由的数据填入 JSONL；字段必须符合 `schemas/` 和 `references/data-routing.md`。

```bash
python3 scripts/scaffold_run_bundle.py \
  --output ./bundles/run-001 \
  --run-id run:example-tech:001 \
  --company-id company:example-tech \
  --result-snapshot-id snapshot:example-tech:001 \
  --mode initial
```

该命令只创建空骨架，不会编造数据。随后按这个顺序填写：

1. `sources.jsonl`：每个不可变来源版本、URL/定位符、版本和 SHA-256；
2. `entities.jsonl`：公司、法人、业务单元、产品等稳定实体；
3. `records.jsonl`：类型化的公开事实或 CRM/合同/工单/使用记录；
4. `events.jsonl`：发生过的阶段变化、发布、签约、工单或用量事件；
5. `evidence.jsonl`：可定位摘录或结构化观察；
6. `claims.jsonl`：原子 Claim、时间、证据、决策和置信度；
7. `relations.jsonl`：由证据支持的实体关系。

可参考 `example/evolving-company/bundles/run-001-public/` 的 JSONL 形状，但必须替换公司 ID、来源、时间和事实，不能直接把合成数据当成真实公司数据。没有数据的集合可以保持为空，但首个运行至少要形成非空的实体、来源、记录、证据、Claim 和运行记录。

### 3. 计算摘要、应用和校验

只有在所有 JSONL 填写完成后，才计算输入摘要。`--complete-now` 会先把 `run.completed_at` 写为当前 UTC 时间，避免脚手架创建后录入的新观察晚于运行完成时间。之后按顺序应用；任何一步报错都应先修复 bundle，不要手工修改规范账本。

```bash
python3 scripts/update_bundle_digest.py ./bundles/run-001 --complete-now
python3 scripts/apply_run.py ./work/example-tech ./bundles/run-001
python3 scripts/validate_company_object.py ./work/example-tech
```

成功后应看到 `当前快照：snapshot:example-tech:001`。`apply_run.py` 会拒绝重复 ID、断裂引用、过期 `base_snapshot_id`、摘要不匹配和非法时间区间。

### 4. 准备增量运行

增量运行必须从当前 manifest 读取基线，不能凭记忆填写。下面命令会创建第二个空 bundle；填充数据后仍需重新计算摘要再应用。

```bash
current_snapshot_id=$(python3 -c \
  'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["current_snapshot_id"])' \
  ./work/example-tech/manifest.json)

python3 scripts/scaffold_run_bundle.py \
  --output ./bundles/run-002 \
  --run-id run:example-tech:002 \
  --company-id company:example-tech \
  --result-snapshot-id snapshot:example-tech:002 \
  --mode incremental \
  --base-snapshot-id "$current_snapshot_id"

# 填写 run-002 的 7 个 JSONL 文件后：
python3 scripts/update_bundle_digest.py ./bundles/run-002 --complete-now
python3 scripts/apply_run.py ./work/example-tech ./bundles/run-002
python3 scripts/validate_company_object.py ./work/example-tech
```

来源更正使用新 Claim 的 `supersedes`，未解决的替代说法使用 `contradicts`；不要编辑已经应用的历史 JSONL 行。

### 5. 导出受众 Skill

规范对象通过校验后，按授权受众导出投影。投影输出目录应是新的目录，不能手工编辑 Markdown 作为事实源。

```bash
python3 scripts/export_company_skill.py ./work/example-tech \
  --audience sales \
  --purpose account-planning \
  --output ./dist/example-tech-sales
python3 scripts/validate_company_skill.py ./dist/example-tech-sales
```

### 6. 只想验证安装是否正常

使用合成示例可以一次性走通三轮运行和四种受众投影；这些数据与现实公司无关：

```bash
python3 scripts/build_evolving_example.py \
  --output ./tmp/evolving-company \
  --force
python3 scripts/validate_company_object.py ./tmp/evolving-company/company-object
python3 scripts/validate_company_skill.py ./tmp/evolving-company/projections/public
```

### 常见报错对应步骤

| 报错或现象 | 原因 | 修复 |
|---|---|---|
| `run.json` 不存在、找不到 `entities.jsonl` | 直接对不存在的 bundle 运行 digest | 先执行 `scaffold_run_bundle.py`，再填写 JSONL |
| `run.input_digest mismatch` | 计算摘要后又改了 bundle | 修改完成后最后再运行一次 `update_bundle_digest.py` |
| `stale base_snapshot_id` | 增量运行基线不是 manifest 当前快照 | 重新读取 `manifest.json`，重建 bundle |
| `unresolved reference` | Claim/证据引用的 ID 没有在同一运行或更早运行中出现 | 先补来源、实体、记录和证据，再补引用它们的 Claim |
| `observed_at is after creating run completed_at` | 数据观察时间晚于 run 完成时间，或填完数据后没有更新运行完成时间 | 最后使用 `update_bundle_digest.py ... --complete-now`，确保所有 `observed_at` 不晚于当前时间 |
| `semantic duplicate` | 新 Claim 与当前 Claim 语义相同但没有生命周期关系 | 用 `supersedes` 明确强化，而不是复制一行 |

运行完整验收：

```bash
python3 scripts/run_acceptance.py --report ./reports/acceptance-report.json
```

## 文档

- [使用手册](references/user-manual.md)
- [概要设计](references/high-level-design.md)
- [系统架构](references/system-architecture.md)
- [公司本体模型](references/company-ontology.md)
- [数据路由](references/data-routing.md)
- [评估标准](references/evaluation-rubric.md)

## 数据安全

不要把真实 CRM 导出、访谈原文、合同、工单、遥测、个人信息或凭据提交到本仓库。生产使用前，应将规范账本迁移到具备事务、加密、认证授权、审计、保留执行和秘密扫描的受控基础设施。

## 许可证

本仓库当前未提供开源许可证，保留全部权利。公开可见不表示已授予复制、修改或分发许可。
