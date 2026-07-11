# Company Distiller（公司蒸馏器）

Company Distiller 把公开资料、CRM、访谈、合同、工单和产品使用数据组织为可重复运行、可追溯、可按受众投影的版本化公司对象。它提供数据契约、增量运行协议、证据与 Claim 生命周期、策略过滤、投影导出和可执行验收。

## 适用范围

本仓库是本地参考实现和语义内核，不是生产级数据安全或合规系统。它不提供数据库事务、跨进程锁、身份认证、文件访问控制、静态加密、租户隔离，也不会自动执行数据保留或删除要求。

规范公司对象与交付 Skill 分离：JSON/JSONL 账本和快照是事实源，Markdown 与受众 Skill 是可重建投影。

## 示例数据声明

`example/evolving-company/` 中的 Northstar Industries、OrbitOps，以及相关 CRM、访谈、合同、工单、使用量、金额和事件均为纯合成测试数据，与任何现实中的同名公司、产品或个人无关。

示例中的 `TEST_ONLY_*_SENTINEL_*` 字符串是固定的投影隔离测试标记，不是密码、令牌或真实业务秘密。公开网址使用保留的 `example.invalid` 域名，数据源连接器标记为 `fixture`。

本项目与任何现实公司、商标权利人或数据提供方不存在关联、授权、背书或代理关系。生成结果不构成法律、投资、采购、网络安全或合规意见。

## 快速开始

```bash
python3 scripts/scaffold_company_skill.py \
  --name "示例科技有限公司" \
  --slug example-tech \
  --output ./company-object

python3 scripts/update_bundle_digest.py ./run-bundle
python3 scripts/apply_run.py ./company-object ./run-bundle
python3 scripts/validate_company_object.py ./company-object

python3 scripts/export_company_skill.py ./company-object \
  --audience sales \
  --output ./sales-company-skill
python3 scripts/validate_company_skill.py ./sales-company-skill
```

运行完整验收：

```bash
python3 scripts/run_acceptance.py
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
