# Windows 本机签到（badarch47/glados_checkin 适配版）

来源：[badarch47/glados_checkin](https://github.com/badarch47/glados_checkin)，2026-11-20 读取的 main 分支；main.js 基于该项目修改，保留账号解析、积分明细、结算统计和失败退出逻辑。浏览器模块为本机普通网页操作适配，未照搬原项目隐藏自动化特征或点击验证码的实现。

## 当前状态

已完成代码准备和离线检查，**尚未在用户的 Windows / 真实账号上实测成功**。安装不等于恢复签到。网站若要求人机验证，需要用户在弹出的 Edge 中操作，无法保证完全无人值守。

## 本机安装

1. 下载仓库 ZIP，解压到固定文件夹，打开本目录。安装后不要移动该目录。
2. 安装 [Node.js 22 LTS 或更高版本](https://nodejs.org/) 和 Microsoft Edge。
3. 在本目录打开 Windows PowerShell，执行 `./Install.ps1`。
4. 按提示分别输入两个账号完整 Cookie（隐藏输入）和各自获取 Cookie 时的 User-Agent。使用普通窗口和独立无痕窗口分别登录两个账号，不要通过退出登录来切换账号；退出会使旧凭证失效。
5. 执行 `./Run.ps1 -TestRun`。两个账号都必须有真实成功/重复响应并通过当天积分流水核验，才算部署完成。

如果组织或系统策略禁止脚本执行，请让本机 Codex 协助诊断具体策略；安装脚本不会更改系统执行策略、浏览器安全设置或网站验证。

## 凭证

凭证保存在 `%LOCALAPPDATA%/GladosLocalCheckin/accounts.xml`，其中 Cookie 使用 Windows DPAPI 按当前用户和机器加密。不会上传到 GitHub，不读取已有 GitHub Secrets。更新凭证运行 `./Configure.ps1`。

## 定时和通知

任务名：`GLaDOS Local Checkin`。每天北京时间 08:47、12:47、18:47、22:47，时间边界固定 +08:00。仅当前 Windows 用户已登录时运行，不要求管理员权限；电脑关机、休眠或用户未登录会影响执行。任务启动时检查今日积分流水，已签到则跳过点击；同一时刻只允许运行一个实例。

成功不弹消息；失败在本机显示弹窗。日志位于 `%LOCALAPPDATA%/GladosLocalCheckin/latest.log`。**本机弹窗不等于 ChatGPT 推送**，原 ChatGPT 兜底任务不自动恢复。

自动积分兑换明确关闭，避免迁移测试时花费积分。需要兑换可另行配置。

## 浏览器行为

使用正常有界面的本机 Edge，只操作匹配且唯一的签到按钮，观察网站自己提交的签到响应并读取今日流水。无匹配或有多个匹配时停止，不猜按钮。不会注入验证码组件、伪造验证码令牌、隐藏 webdriver、改变网络出口或自动点击人机验证。出现验证时可在真实 Edge 窗口中手动处理；90 秒未取得确定结果则失败退出。

## 卸载

运行：`Unregister-ScheduledTask -TaskName 'GLaDOS Local Checkin' -Confirm:$false`。随后可自行删除本机配置文件夹。脚本不会自动删除凭证或日志。

## 验证记录

离线测试覆盖 Cookie 等号保留、非法格式拒绝、按钮歧义拒绝、北京时间自然日计算。云端环境不具备 Windows Task Scheduler 和真实账号登录条件，PowerShell 注册任务、Edge 页面实际按钮及真实签到均待本机验收。
