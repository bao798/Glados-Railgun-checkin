"""Public university notices -> durable pending queue -> SMTP digest. Stdlib only."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
import posixpath
from pathlib import Path
import re
import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
ARTICLE = re.compile(r'/info/|/news/|/post/|/art/|/[a-f0-9]{24,32}\.htm|/\d{4}/\d{1,2}|/t\d{8}_|/c\d+a\d+/|/\w*article\w*/|/\w*detail\w*|[?&](?:id|keyId|articleId|newsid)=\w+|/\d{5,}\.(?:htm|html)', re.I)
CATEGORY = re.compile(r'推免|免试|夏令营|开放日|硕士招生|招生信息|招生公告|通知公告|招生动态|招生工作|最新公告')

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.current, self.current_tag = [], None, None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        match = re.search(r"window\.open\(['\"]([^'\"]+)", a.get('onclick', ''))
        if tag == 'a' or match:
            self.finish()
            self.current_tag = tag
            self.current = [a.get('href', '') or (match[1] if match else ''), a.get('title', ''), []]
    def handle_data(self, data):
        if self.current:
            self.current[2].append(data)
    def handle_endtag(self, tag):
        if tag == self.current_tag:
            self.finish()
    def finish(self):
        if self.current:
            href, title, pieces = self.current
            title = re.sub(r'\s+', ' ', title or ''.join(pieces)).strip()
            self.links.append((href, title))
            self.current = None
            self.current_tag = None


def fetch(url, token=None):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; UniversityNoticeMonitor/1.0)'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
        headers['Accept'] = 'application/vnd.github+json'
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers=headers), timeout=18) as r:
                body = r.read(3_000_001)
                if len(body) > 3_000_000:
                    raise ValueError('page too large')
                charset = r.headers.get_content_charset()
                if not charset:
                    m = re.search(br'charset\s*=\s*["\']?([\w-]+)', body[:4096], re.I)
                    charset = m[1].decode('ascii') if m else 'utf-8'
                return body.decode(charset, errors='replace'), r.url
        except Exception:
            if attempt:
                raise
            time.sleep(1)


def canonical(url):
    p = urlsplit(url)
    path = posixpath.normpath('/' + p.path.lstrip('/'))
    if p.path.endswith('/') and path != '/':
        path += '/'
    return urlunsplit((p.scheme, p.netloc.lower(), path, p.query, ''))


def scan(source, config):
    items, errors, visited = {}, [], set()
    queue = [source['url']]
    host = urlsplit(source['url']).hostname
    while queue and len(visited) < 4:
        page = queue.pop(0)
        if page in visited:
            continue
        visited.add(page)
        try:
            body, actual = fetch(page)
            parser = Links()
            parser.feed(body)
            parser.finish()
            # Some official landing pages redirect with a literal JS URL.
            redirect = re.search(r'window\.location(?:\.href)?\s*=\s*[\"\']([^\"\']+)', body)
            if not parser.links and redirect:
                target = canonical(urljoin(actual, redirect[1]))
                if urlsplit(target).hostname == host and urlsplit(target).scheme in ('http', 'https'):
                    if target not in visited and target not in queue:
                        queue.append(target)
            for href, title in parser.links:
                url = canonical(urljoin(actual, href))
                if urlsplit(url).scheme not in ('http', 'https') or not title:
                    continue
                if ARTICLE.search(url) and len(title) >= 8 and urlsplit(url).hostname == host:
                    items[url] = {'title': title, 'url': url, 'source': source['name']}
                elif CATEGORY.search(title) and len(title) < 22 and urlsplit(url).hostname == host:
                    if url not in visited and url not in queue:
                        queue.append(url)
        except Exception as e:
            code = getattr(e, 'code', None)
            errors.append(type(e).__name__ + (f' {code}' if code else '') + ' @ ' + page)
    relevant = [x for x in items.values() if source.get('all_notices') or any(k in x['title'] for k in config['keywords'])]
    for x in relevant:
        x['priority'] = any(k in x['title'] for k in config['priority_keywords'])
        x['urgent'] = any(k in x['title'] for k in config['urgent_keywords'])
        x['fingerprint'] = hashlib.sha256((x['url'] + '\n' + x['title']).encode()).hexdigest()
    status = 'ok' if items and not errors else 'partial' if items else 'error'
    return source['name'], relevant, {'status': status, 'articles': len(items), 'matched': len(relevant), 'pages': len(visited), 'errors': errors or ([] if items else ['NoArticleLinks'])}


def ingest(state, source, items, now):
    initialized = source in state['initialized']
    unseen = [x for x in items if x['fingerprint'] not in state['seen']]
    for x in items:
        state['seen'][x['fingerprint']] = now.isoformat()
    # First scan: queue a limited reference sample; never flood old announcements as urgent.
    for x in unseen if initialized else unseen[:3]:
        x = dict(x, discovered=now.isoformat(), baseline=not initialized)
        state['pending'][x['fingerprint']] = x
    state['initialized'][source] = now.isoformat()


def glados_health(now):
    repo, token = os.getenv('GITHUB_REPOSITORY'), os.getenv('GITHUB_TOKEN')
    if not repo or not token:
        return '未读取 GitHub 签到记录（本地预览）'
    try:
        body, _ = fetch(f'https://api.github.com/repos/{repo}/actions/workflows/glados-scheduled-checkin.yml/runs?per_page=20', token)
        runs = json.loads(body)['workflow_runs']
        today = [r for r in runs if dt.datetime.fromisoformat(r['created_at'].replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Shanghai')).date() == now.date()]
        scheduled = [r for r in today if r['event'] == 'schedule']
        success = [r for r in today if r['conclusion'] == 'success']
        text = f'今日签到工作流 {len(today)} 次，成功 {len(success)} 次；原生定时触发 {len(scheduled)} 次。'
        if today:
            text += '\n最新运行：' + str(today[0]['conclusion'] or today[0]['status']) + '\n' + today[0]['html_url']
        if not success:
            text += '\n警告：尚无今日成功记录，请核对 Cookie / 工作流。'
        if not scheduled:
            text += '\n警告：今日尚未验证原生定时触发。'
        return text
    except Exception as e:
        return '签到记录读取失败：' + type(e).__name__


def render(items, health, status, now, kind):
    ordered = sorted(items, key=lambda x: (not x['priority'], not x['urgent'], x['source']))
    lines = [f'大学生私人自动化系统｜{kind}｜{now:%Y-%m-%d %H:%M} 北京时间', '', 'GLaDOS', health, '', f'通知 {len(ordered)} 条（按标题分类；首次样本可能为历史通知）']
    blocks = []
    for x in ordered:
        tags = ('[重点方向] ' if x['priority'] else '') + ('[首次参考/请核对日期] ' if x['baseline'] else '[新发现/更新] ')
        lines.extend(['', tags + x['source'] + '：' + x['title'], x['url']])
        blocks.append('<li>' + html.escape(tags + x['source'] + '：') + '<a href="' + html.escape(x['url'], quote=True) + '">' + html.escape(x['title']) + '</a></li>')
    bad = {n: v for n,v in status.items() if v['status'] != 'ok'}
    lines.extend(['', f'来源检查：正常 {len(status)-len(bad)}/{len(status)}'])
    for n,v in bad.items():
        lines.append(n + '：' + v['status'] + ' / ' + ', '.join(v['errors']))
    lines.extend(['', '覆盖已配置的官网入口及最多3个同站栏目；不代表所有院系/研究所全覆盖。未读取通知正文，报名条件和截止时间请点击原文确认。'])
    plain = '\n'.join(lines)
    rich = '<html><body><h2>大学生私人自动化系统</h2><pre>' + html.escape('\n'.join(lines[:7])) + '</pre><ol>' + ''.join(blocks) + '</ol><pre>' + html.escape('\n'.join(lines[-len(bad)-4:])) + '</pre></body></html>'
    return plain, rich


def send_mail(subject, plain, rich):
    user, password, recipient = (os.getenv(x, '') for x in ['SMTP_USER','SMTP_PASSWORD','EMAIL_TO'])
    if not all((user, password, recipient)):
        raise ValueError('缺少 SMTP_USER、SMTP_PASSWORD 或 EMAIL_TO Secret')
    msg = EmailMessage()
    msg['Subject'], msg['From'], msg['To'] = subject, user, recipient
    msg.set_content(plain)
    msg.add_alternative(rich, subtype='html')
    with smtplib.SMTP_SSL(os.getenv('SMTP_HOST') or 'smtp.qq.com', int(os.getenv('SMTP_PORT') or '465'), context=ssl.create_default_context(), timeout=30) as server:
        server.login(user, password)
        server.send_message(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', action='store_true', help='fetch and render only; no email or state mutation')
    ap.add_argument('--force-digest', action='store_true')
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    now = dt.datetime.now(ZoneInfo('Asia/Shanghai'))
    config = json.loads((BASE/'sources.json').read_text())
    state_dir = Path(os.getenv('STATE_DIR', str(BASE/'state')))
    state_path = state_dir/'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'seen': {}, 'pending': {}, 'initialized': {}, 'last_digest': '', 'alerted': []}
    status = {}
    sources = config['sources'][:args.limit] if args.limit else config['sources']
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(scan, source, config) for source in sources]
        for future in concurrent.futures.as_completed(futures):
            name, items, health = future.result()
            status[name] = health
            if health['articles']:
                ingest(state, name, items, now)
            print(name, health['status'], health['articles'], health['matched'], flush=True)
    health = glados_health(now)
    daily = args.force_digest or (now.hour >= 21 and state['last_digest'] != now.date().isoformat())
    pending = list(state['pending'].values())
    alerted = set(state['alerted'])
    items = pending if daily or args.preview else [x for x in pending if x['urgent'] and not x['baseline'] and x['fingerprint'] not in alerted]
    kind = '每日汇总' if daily or args.preview else '保研新通知'
    plain, rich = render(items, health, status, now, kind)
    out = BASE/'output'
    out.mkdir(exist_ok=True)
    (out/'digest.txt').write_text(plain)
    (out/'digest.html').write_text(rich)
    (out/'health.json').write_text(json.dumps(status, ensure_ascii=False, indent=2))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write('## 大学生私人自动化系统\n\n' + plain + '\n')
    mail_failed = False
    if not args.preview and (daily or items):
        try:
            send_mail(f'【大学助手】{kind} {now:%m-%d} · {len(items)} 条', plain, rich)
            if daily:
                state['last_digest'] = now.date().isoformat()
                state['pending'].clear()
                state['alerted'] = []
            else:
                state['alerted'] = list(alerted | {x['fingerprint'] for x in items})
            print('Mail accepted by SMTP server (receipt not yet verified).')
        except Exception as e:
            print('邮件未发送：' + type(e).__name__ + '；检查 SMTP Secrets / 服务器。待发队列已保留。')
            mail_failed = True
    if not args.preview:
        state_dir.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp.replace(state_path)
    if mail_failed or any(v['status'] != 'ok' for v in status.values()):
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
