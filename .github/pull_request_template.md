## 变更说明

<!-- 用中文说明本 PR 解决的问题和用户可见变化。不要粘贴密码、Token、API Key 或 Vault 私密内容。 -->

## 影响范围

- [ ] 后端 API / Agent
- [ ] 检索或评测
- [ ] 前端页面
- [ ] Docker / PostgreSQL / Redis
- [ ] 文档或发布资产

## 验证记录

- [ ] `python -m pytest backend/tests evaluation/tests -q`
- [ ] `python evaluation/scripts/validate_mvp_dataset.py`
- [ ] `npm run build --prefix frontend`
- [ ] 已完成相关浏览器 smoke 或说明无法完成的原因

## 安全检查

- [ ] 未提交 `.env`、Token、API Key、密码、Cookie 或私钥
- [ ] 外部写入仍经过预览/审批和权限检查
- [ ] 外部 Obsidian Vault 未被修改
- [ ] 已确认 staged 文件范围只包含本 PR 需要的文件

## 截图或接口证据

<!-- 页面变更请附截图/GIF；API 变更请附脱敏请求和响应摘要。 -->
