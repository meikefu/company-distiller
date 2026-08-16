# 比亚迪蒸馏执行记录

本次运行按 `company-distiller/SKILL.md` 的规范完成，目标对象为 `company:byd`，边界为比亚迪股份有限公司及公开披露的合并口径业务信息。

## 已执行步骤

以下命令均在 `company-distiller/` 目录执行。

```bash
# 1. 生成公开来源运行包
python3 scripts/build_byd_bundles.py \
  --raw ./byd-research/raw \
  --output ./byd-bundles

# 2. 对每个不可变 bundle 计算输入摘要
python3 scripts/update_bundle_digest.py ./byd-bundles/run-001-public-foundation
python3 scripts/update_bundle_digest.py ./byd-bundles/run-002-july-2026-sales

# 3. 初始化规范公司对象
python3 scripts/scaffold_company_skill.py \
  --name "比亚迪" \
  --slug byd \
  --output ./byd-company \
  --date 2026-08-16 \
  --force

# 4. 按基线顺序应用初始运行和增量运行
python3 scripts/apply_run.py ./byd-company ./byd-bundles/run-001-public-foundation
python3 scripts/apply_run.py ./byd-company ./byd-bundles/run-002-july-2026-sales

# 5. 校验规范对象
python3 scripts/validate_company_object.py ./byd-company

# 6. 导出公开研究投影并校验
python3 scripts/export_company_skill.py ./byd-company \
  --audience public \
  --output ./byd-projections/public
python3 scripts/validate_company_skill.py ./byd-projections/public

# 7. 回归测试与参考实现发布门禁
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/run_acceptance.py \
  --report ./byd-research/company-distiller-acceptance-report.json
```

## 运行结果

- `run:byd:001` -> `snapshot:byd:001`，快照哈希：`sha256:9f5fed37ac09132ccf50da4c94a2f2381f494b674b7262ea3d97ef06deed648e`
- `run:byd:002` -> `snapshot:byd:002`，快照哈希：`sha256:cd7422b36cb9c4a22f1f0ce7ddb8f070e587c1dce082d089b8d0c825dda761a8`
- 规范对象：2 次运行、2 个快照、18 条当前 Claim、10 个证据单元
- 公开投影：18 条当前 Claim、10 个证据单元，`projection:byd:002:public`
- 单元测试：5/5 通过
- Company Distiller 发布门禁：16/16 通过

## 来源指纹

| 来源 | SHA-256 |
|---|---|
| 2025 年报 PDF | `sha256:7906b6647eb7cf3ab5986e9b8eda8f707969c64dc54c67b83b606744ef9f4846` |
| About BYD 页面快照 | `sha256:e8de5c8c4fa2f6c34571c79446942deadb1194993f789e6ad66c14c764fbdfbf` |
| 2026 年 7 月产销公告 PDF | `sha256:e699fcee3273143e19a290e02ad8b77080d032c896c66b610cb2e8c00f8b2ec4` |

## 更新规则

后续刷新时不要编辑 `byd-company` 中已有 JSONL 行。读取 `manifest.json` 的 `current_snapshot_id`，准备新的增量 bundle，把 `base_snapshot_id` 设置为该值，重新运行 `update_bundle_digest.py`，再应用、校验并重新导出投影。来源更正使用新 Claim 的 `supersedes` 或 `contradicts`；未经审计的经营数据在正式披露替代前保持原始状态和时间范围。

本次没有 CRM、访谈、合同、工单或产品使用数据，因此投影不会回答采购意向、产品采纳、满意度或客户健康度等问题；这些问题需要直接授权且可追溯的数据源。
