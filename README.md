# GLaDOS Windows 本机签到

已根据用户选择，迁移至 [badarch47/glados_checkin](https://github.com/badarch47/glados_checkin) 的本机适配方案。

**入口：[windows-checkin/README.md](windows-checkin/README.md)**

旧 Python 签到 job 已禁用；原工作流的维护 job 保留。旧 GitHub Secrets 未读取、复制或修改，新的本机配置需要由用户在本机输入并使用 Windows DPAPI 加密保存。

本机安装与真实账号验收尚未完成，不能把代码迁移视为自动签到已恢复。正常签到保持安静；失败在 Windows 本机弹窗，ChatGPT 兜底不自动恢复。
