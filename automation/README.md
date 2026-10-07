# 大学生私人自动化系统

系统位于现有 bao798/Glados-Railgun-checkin 仓库。已有 GLaDOS 工作流继续签到和兑换；本系统读取其当日运行结果并纳入邮件，避免新增重复签到链路。

## 覆盖

- 39所985高校：sources.json 列出的校级研招入口及最多3个同站招生栏目。
- 国科大招生网；中科院数学院、计算所、自动化所入口。
- 吉大数学学院、本科生院、考试工作办公室。
- 不保证覆盖所有院系、中科院全部研究所、登录后公告、公众号或JS动态内容。来源抓取失败/没有解析到文章/部分栏目失败都会显示异常，不能视为无通知。
- 按标题关键词筛选、排序，优先显示统计/数学/计算机/AI/金融相关标题，其余保研通知仍保留。链接与标题更新可识别；仅正文发生变化暂不识别。

## 启用QQ邮箱推送

在仓库 Settings → Secrets and variables → Actions → New repository secret 新增：

| Secret | 内容 |
|---|---|
| SMTP_USER | 发信QQ邮箱完整地址（可与收件地址相同） |
| SMTP_PASSWORD | QQ邮箱SMTP授权码，不能填QQ密码 |
| EMAIL_TO | 你的QQ收件邮箱地址 |

默认 smtp.qq.com:465 / SSL。可通过 Actions Variables 设置 SMTP_HOST / SMTP_PORT。不要把邮箱、授权码或 Cookie 写进公开代码或聊天。现有 GLADOS_COOKIES 无需重新配置。

然后 Actions → University private automation → Run workflow → mode=digest。确认收到邮件；若失败查看日志中异常类型与来源状态，不输出凭据。手机QQ邮箱登录收件账号并启用应用通知、系统通知和后台接收。

## 时刻（北京时间）

08:37—22:37 每小时抓取一次；21:37起，当天首次运行发送日报。21时那次延迟时，22时的运行会补发。workflow_dispatch 的 digest 模式始终强制发一封测试/日报；preview 不发邮件、不写持久状态。

GitHub schedule 是尽力调度，可能延迟或丢弃；电脑关机不影响云端运行，但不能承诺准点/不漏触发。仅手动/推送测试成功不等于定时触发已验证恢复。原生 schedule 的实际记录需要另行确认。

首次扫描只将每来源最多3条作为历史参考样本，不发送历史公告的即时提醒。以后新发现的推免/夏令营/开放日等通知即时邮件提醒，其他变化留到日报。即时提醒记录仍会出现在当日汇总。失败不清空队列、不标记已发送。SMTP接受与实际进收件箱不同，首次需验证邮箱。极少数邮件已接受但状态保存失败的情况可能重复。

## 状态与报告

持久状态存放 automation-state 分支；只含公开通知链接、标题、发现时间与发送标记，不含邮箱、Cookie、GLaDOS剩余天数、凭据。每次运行都有 Actions Summary 与7天报告artifact。运行结果：任何来源异常/邮件失败会变红，同时尽可能保留队列。

本地预览：`python automation/run.py --preview`（Python 3.10+，仅标准库）。本地默认状态目录为 automation/state。测试：`python -m unittest discover -s automation/tests`。

扩展来源：编辑 sources.json；校内通知可设 all_notices=true，其他来源按 keywords 筛选。暂时只接入已知GLaDOS签到，其他网站需要明确网址和登录方式后编写适配器；本系统不会对未知网站提交签到请求。
