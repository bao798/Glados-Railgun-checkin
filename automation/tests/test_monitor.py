import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('monitor', Path(__file__).parents[1]/'run.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MonitorTests(unittest.TestCase):
    def test_parse_links_and_escaped_title(self):
        p = m.Links(); p.feed('<a href="info/1/2.htm" title="推免 &amp; 夏令营"><span>短标题</span></a>')
        self.assertEqual(p.links, [('info/1/2.htm','推免 & 夏令营')])
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
    def test_render_escapes_untrusted_titles(self):
        item={'title':'<script>alert(1)</script>','url':'https://a/','source':'a','priority':True,'urgent':True,'baseline':False}
        _, rich=m.render([item],'ok',{},dt.datetime.now(),'test')
        self.assertNotIn('<script>',rich)
    def test_missing_smtp_does_not_send(self):
        with patch.dict(m.os.environ,{},clear=True):
            with self.assertRaises(ValueError):m.send_mail('t','t','t')
    def test_39_schools(self):
        cfg=m.json.loads((m.BASE/'sources.json').read_text())
        self.assertEqual(sum(s['group']=='985' for s in cfg['sources']),39)
        self.assertEqual(len({s['name'] for s in cfg['sources']}),len(cfg['sources']))

if __name__=='__main__':unittest.main()
