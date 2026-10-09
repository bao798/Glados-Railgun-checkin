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

08:37—22:37 每小时抓取一次；21:37起，当天首次运行发送日报。21时那次延迟时，22时的运行会补发。workflow_dispatch 的 digest 模式可提前发送当日日报，但当天已发送则跳过；preview 不发邮件、不写持久状态。

GitHub schedule 是尽力调度，可能延迟或丢弃；电脑关机不影响云端运行，但不能承诺准点/不漏触发。仅手动/推送测试成功不等于定时触发已验证恢复。原生 schedule 的实际记录需要另行确认。

首次扫描只将每来源最多3条作为历史参考样本，不发送历史公告的即时提醒。所有新发现的通知（包括推免/夏令营/开放日）均留到每日汇总，不发送即时提醒。按北京时间日期去重，每天最多自动发送一封日报；当天已发送时，主计划、备用链路和手动 digest 均跳过。mail-test 仅在用户主动选择时独立发送测试邮件。失败不清空队列、不标记已发送。SMTP接受与实际进收件箱不同，首次需验证邮箱。极少数邮件已接受但状态保存失败的情况可能重复。

## 状态与报告

持久状态存放 automation-state 分支；只含公开通知链接、标题、发现时间与发送标记，不含邮箱、Cookie、GLaDOS剩余天数、凭据。每次运行都有 Actions Summary 与7天报告artifact。运行结果：任何来源异常/邮件失败会变红，同时尽可能保留队列。

本地预览：`python automation/run.py --preview`（Python 3.10+，仅标准库）。本地默认状态目录为 automation/state。测试：`python -m unittest discover -s automation/tests`。

扩展来源：编辑 sources.json；校内通知可设 all_notices=true，其他来源按 keywords 筛选。暂时只接入已知GLaDOS签到，其他网站需要明确网址和登录方式后编写适配器；本系统不会对未知网站提交签到请求。

## 官网适配

支持上交 post 链接、中科大 onclick 链接、北理工及西农长文章编号、国防科大同站 JavaScript 跳转、中科院带 ../ 的栏目路径。浙大当前采用可访问的官网 HTTP 公告入口，只读取公开信息。任何入口异常仍会在报告里显示；工作流先执行解析与发送保护测试。

## Google 邮箱

收件邮箱与发信邮箱相互独立。只改为 Gmail 收信时，把 EMAIL_TO Secret 换为 Gmail 地址，继续配置 QQ 发信地址和 QQ SMTP 授权码即可。

若使用 Gmail 发信：SMTP_USER Secret 填 Gmail 完整地址；SMTP_PASSWORD Secret 填 Google 应用专用密码；EMAIL_TO Secret 填收件地址。在 Actions Variables 中设置 SMTP_HOST=smtp.gmail.com、SMTP_PORT=465（SSL）。Google 应用专用密码要求启用两步验证，部分组织账户可能不支持。参考：https://support.google.com/accounts/answer/185833 。

配置后 Actions → University private automation → Run workflow → mode=mail-test，仅发送一封测试邮件，不抓取官网、不读写通知队列。缺少配置会明确列出缺少的 Secret 名称，不打印凭据。SMTP 接受后仍需确认收件箱实际收到，再运行 mode=digest 初始化监控并验证日报。

## 定时触发与补发保护

主链路按北京时间 08:37—22:37 每小时执行，21:37 起按日期去重发送日报。备用链路由 GLaDOS scheduled checkin 的原生 schedule 运行完成触发学校监控，推送提交引起的签到运行不会启动监控。GLaDOS 22:17 的定时运行可补发当日尚未发送的日报。两条链路共用 university-assistant 并发组与 automation-state 分支，串行处理相同待发队列。签到工作流的定时保活任务还会检查并重新启用学校工作流；学校自身也检查启用状态。GitHub 调度仍属于尽力服务，两条链路不能消除平台整体故障。
