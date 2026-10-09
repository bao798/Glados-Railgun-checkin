import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import json
spec = importlib.util.spec_from_file_location('monitor', Path(__file__).parents[1]/'run.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MonitorTests(unittest.TestCase):
    def test_parse_links_and_escaped_title(self):
        p = m.Links(); p.feed('<a href="info/1/2.htm" title="推免 &amp; 夏令营"><span>短标题</span></a>')
        self.assertEqual(p.links, [('info/1/2.htm','推免 & 夏令营')])
    def test_school_specific_urls(self):
        for url in ['https://yzb.sjtu.edu.cn/post/1','https://yz.cqu.edu.cn/news/2026-09/2600.html','https://grd.bit.edu.cn/zsgz/1f63040825294e62b5cc2889b5ef49e5.htm','https://yz.cau.edu.cn/art/2026/9/5/art_1_2.html']:
            self.assertIsNotNone(m.ARTICLE.search(url))
        p=m.Links(); p.feed("<div onclick=\"window.open('/article/2853/182','_blank')\">推免报名通知</div>")
        self.assertEqual(p.links,[('/article/2853/182','推免报名通知')])
    def test_baseline_duplicate_and_update(self):
        state={'seen':{},'pending':{},'initialized':{}}
        now=dt.datetime.now(dt.timezone.utc)
        items=[{'fingerprint':str(i),'title':'推免','url':'https://a/info/1/2.htm','source':'a','urgent':True,'priority':False} for i in range(5)]
        m.ingest(state,'a',items,now)
        self.assertEqual(len(state['pending']),3)
        self.assertTrue(all(x['baseline'] for x in state['pending'].values()))
        m.ingest(state,'a',items,now)
        self.assertEqual(len(state['pending']),3)
        m.ingest(state,'a',[dict(items[0],fingerprint='updated')],now)
        self.assertFalse(state['pending']['updated']['baseline'])
    def test_unparseable_page_is_failure(self):
        with patch.object(m,'fetch',return_value=('<html>verification required</html>','https://a/')):
            _, items, health=m.scan({'name':'a','url':'https://a/'},{'keywords':[],'priority_keywords':[],'urgent_keywords':[]})
        self.assertEqual(health['status'],'error')
        self.assertEqual(items,[])
    def test_normalize_cas_navigation(self):
        self.assertEqual(m.canonical('https://amss.cas.cn/../../admission/sszs/#x'), 'https://amss.cas.cn/admission/sszs/')
        self.assertIsNotNone(m.ARTICLE.search('https://yz.nwafu.edu.cn/tzgg/efc5ad22976f45b595487499b6c39d8e.htm'))
    def test_same_host_js_redirect(self):
        pages=[('<script>window.location.href="/index/new-index.view";</script>','https://a/'),('<a href="/detail/123">2027年推免报名通知</a>','https://a/index/new-index.view')]
        with patch.object(m,'fetch',side_effect=pages):
            _, items, health=m.scan({'name':'a','url':'https://a/'},{'keywords':['推免'],'priority_keywords':[],'urgent_keywords':['推免']})
        self.assertEqual(health['status'],'ok')
        self.assertEqual(len(items),1)
    def test_external_js_redirect_not_followed(self):
        with patch.object(m,'fetch',return_value=('<script>window.location.href="https://other/";</script>','https://a/')) as fetch:
            _, _, health=m.scan({'name':'a','url':'https://a/'},{'keywords':[],'priority_keywords':[],'urgent_keywords':[]})
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(health['status'],'error')
    def test_render_escapes_untrusted_titles(self):
        item={'title':'<script>alert(1)</script>','url':'https://a/','source':'a','priority':True,'urgent':True,'baseline':False}
        _, rich=m.render([item],'ok',{},dt.datetime.now(),'test')
        self.assertNotIn('<script>',rich)
    def test_missing_smtp_does_not_send(self):
        with patch.dict(m.os.environ,{},clear=True):
            with self.assertRaises(ValueError):m.send_mail('t','t','t')
    def test_mail_test_missing_credentials_does_not_scan(self):
        with patch.dict(m.os.environ,{},clear=True), patch.object(m.sys,'argv',['run.py','--test-mail']), patch.object(m,'fetch') as fetch, patch.object(m,'send_mail') as send:
            self.assertEqual(m.main(),1)
        fetch.assert_not_called()
        send.assert_not_called()
    def test_mail_test_sends_without_scanning(self):
        with patch.dict(m.os.environ,{'SMTP_USER':'sender@gmail.com','SMTP_PASSWORD':'example','EMAIL_TO':'receiver@gmail.com'},clear=True), patch.object(m.sys,'argv',['run.py','--test-mail']), patch.object(m,'fetch') as fetch, patch.object(m,'send_mail') as send:
            self.assertEqual(m.main(),0)
        fetch.assert_not_called()
        send.assert_called_once()
    def test_daily_only_delivery_and_retry(self):
        real_datetime = dt.datetime
        item = {'fingerprint': 'urgent', 'title': '推免通知', 'url': 'https://a/', 'source': 'a', 'urgent': True, 'priority': True, 'baseline': False}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'sources.json').write_text(json.dumps({'sources': []}))
            state_path = root/'state.json'
            state_path.write_text(json.dumps({'seen': {}, 'pending': {'urgent': item}, 'initialized': {}, 'last_digest': '', 'alerted': []}))
            with patch.object(m, 'BASE', root), patch.dict(m.os.environ, {'STATE_DIR': folder}, clear=True), patch.object(m, 'glados_health', return_value='ok'), patch.object(m, 'send_mail') as send:
                def invoke(hour, force=False):
                    now = real_datetime(2026, 10, 9, hour, 37, tzinfo=m.ZoneInfo('Asia/Shanghai'))
                    with patch.object(m.dt, 'datetime') as clock, patch.object(m.sys, 'argv', ['run.py'] + (['--force-digest'] if force else [])):
                        clock.now.return_value = now
                        return m.main()
                self.assertEqual(invoke(10), 0)
                send.assert_not_called()
                self.assertIn('urgent', json.loads(state_path.read_text())['pending'])
                send.side_effect = RuntimeError('SMTP unavailable')
                self.assertEqual(invoke(21), 1)
                self.assertEqual(json.loads(state_path.read_text())['last_digest'], '')
                send.side_effect = None
                self.assertEqual(invoke(22), 0)
                self.assertEqual(send.call_count, 2)
                self.assertEqual(json.loads(state_path.read_text())['last_digest'], '2026-10-09')
                self.assertEqual(invoke(22), 0)
                self.assertEqual(invoke(22, force=True), 0)
                self.assertEqual(send.call_count, 2)
    def test_39_schools(self):
        cfg=m.json.loads((m.BASE/'sources.json').read_text())
        self.assertEqual(sum(s['group']=='985' for s in cfg['sources']),39)
        self.assertEqual(len({s['name'] for s in cfg['sources']}),len(cfg['sources']))

if __name__=='__main__':unittest.main()
