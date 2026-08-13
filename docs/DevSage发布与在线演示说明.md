# DevSage 发布与在线演示说明

## 当前状态

更新时间：2026-08-13 20:30

- GitHub CI：`.github/workflows/ci.yml`，检查后端、75 道评测问题和前端构建。
- 版本发布：`.github/workflows/release.yml`，推送 `v*.*.*` 标签后生成源码加前端构建产物的 Release 压缩包。
- 本地演示入口：`http://127.0.0.1:5173/`。
- 在线演示入口：暂未部署，不能在 README 中伪造公网地址；部署后只需把真实地址补到 README 的入口区域。

## 本地演示

```powershell
.\scripts\start-demo.ps1
Start-Process http://127.0.0.1:5173/
```

如果要连接外部只读 Obsidian Vault：

```powershell
.\scripts\start-demo.ps1 -ObsidianVaultPath "D:\zzd_project\cursor\life\Obsidian Vault"
```

## 发布流程

1. 在 `main` 上完成测试和浏览器验证。
2. 创建中文提交并推送到 GitHub。
3. 创建版本标签，例如 `git tag v0.2.0`。
4. 推送标签：`git push origin v0.2.0`。
5. GitHub Actions 会构建 `frontend/dist`，打包后端、评测集、文档和样例数据，并创建 Release。

发布包不包含 `.env`、`data/`、模型权重、用户认证文件或任何本地凭据。

## 截图与 GIF

- 已提交截图：[feedback-loop-fixed.png](assets/feedback-loop-fixed.png)，展示答案反馈、引用勾选和提交状态。
- 浏览器验证命令和输出目录见 `scripts/verify-browser.ps1` 与 `output/playwright/`。
- GIF 录制建议使用 Playwright CLI 的 `video-start` / `video-stop`，录制“选择知识库示例 → 开始排查 → 查看答案 → 提交反馈”的短流程；录制后只保留脱敏画面，再放入 `docs/assets/`。
