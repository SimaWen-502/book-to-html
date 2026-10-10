"""Small synthetic inputs exercise resource controls and real rendering boundaries."""
import contextlib,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from extract_book import BoundedZip,extract
from render_book import render
from validate_book import check,Audit
from check_release import inspect

class ArchiveTests(unittest.TestCase):
    def archive(self,items):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,content in items:z.writestr(name,content)
        data.seek(0);return zipfile.ZipFile(data)
    def test_member_limit_before_read(self):
        with self.archive([('large',b'x'*65)]) as z:
            class Small(BoundedZip):MAX_MEMBER_BYTES=64
            with self.assertRaises(ValueError):Small(z)
    def test_total_limit_before_read(self):
        with self.archive([('a',b'x'*33),('b',b'y'*33)]) as z:
            class Small(BoundedZip):MAX_TOTAL_BYTES=64
            with self.assertRaises(ValueError):Small(z)
    def test_member_count_limit(self):
        with self.archive([('a',b'a'),('b',b'b')]) as z:
            class Small(BoundedZip):MAX_MEMBERS=1
            with self.assertRaises(ValueError):Small(z)
    def test_actual_stream_limit_ignores_forged_metadata(self):
        class Fake:
            def infolist(self):return []
            def open(self,name):return io.BytesIO(b'x'*65)
        class Small(BoundedZip):MAX_MEMBER_BYTES=64
        with self.assertRaises(ValueError):Small(Fake()).read('a')
    def test_cumulative_repeated_reads(self):
        with self.archive([('a',b'x'*33)]) as z:
            class Small(BoundedZip):MAX_TOTAL_BYTES=64
            bounded=Small(z);self.assertEqual(bounded.read('a'),b'x'*33)
            with self.assertRaises(ValueError):bounded.read('a')
    def test_valid_docx_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'book.docx'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>原创测试段落</w:t></w:r></w:p></w:body></w:document>')
            with contextlib.redirect_stdout(io.StringIO()):data=extract(source,root/'out')
            self.assertEqual(data['segments'][0]['paragraphs'][0]['text'],'原创测试段落')
            self.assertEqual(data['source_path'],'book.docx')
    def test_valid_epub_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'book.epub'
            with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>')
                z.writestr('content.opf','<package><metadata><title>原创测试</title></metadata><manifest><item id="c" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c"/></spine></package>')
                z.writestr('chapter.xhtml','<html><body><p>一个可回查的测试段落。</p></body></html>')
            with contextlib.redirect_stdout(io.StringIO()):data=extract(source,root/'out')
            self.assertEqual(data['segments'][0]['paragraphs'][0]['text'],'一个可回查的测试段落。')
            self.assertEqual(data['source_path'],'book.epub')

class WorkflowTests(unittest.TestCase):
    def fixture(self,genre='nonfiction'):
        folder=ROOT/'examples'/genre
        return json.loads((folder/'source'/'source.json').read_text(encoding='utf-8')),json.loads((folder/'knowledge.json').read_text(encoding='utf-8'))
    def test_original_examples_validate_and_remain_offline(self):
        for genre in ('nonfiction','fiction'):
            with self.subTest(genre=genre):
                s,k=self.fixture(genre);folder=ROOT/'examples'/genre
                self.assertTrue(check(s,k,folder)['passed'])
                audit=Audit();audit.feed((folder/'index.html').read_text(encoding='utf-8'))
                self.assertFalse(audit.external)
                self.assertEqual(len(audit.ids),len(set(audit.ids)))
                self.assertTrue(all(x in audit.ids for x in audit.links))
    def test_broken_source_pointer_blocks_render(self):
        s,k=self.fixture();k['units'][0]['points'][0]['refs'][0]['paragraphs']=['P9999']
        self.assertFalse(check(s,k,ROOT)['passed'])
    def test_markup_and_script_terminator_are_data(self):
        s,k=self.fixture();payload='</script><img src=x onerror="window.bookInjected=true">'
        k['title']=payload;k['units'][0]['lead']=payload
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sp=root/'source.json';kp=root/'knowledge.json';hp=root/'index.html'
            sp.write_text(json.dumps(s,ensure_ascii=False),encoding='utf-8');kp.write_text(json.dumps(k,ensure_ascii=False),encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):render(sp,kp,hp)
            content=hp.read_text(encoding='utf-8')
            self.assertNotIn(payload,content)
            self.assertIn('&lt;/script&gt;',content)
            self.assertIn('\\u003c/script>',content)
    def test_spoiler_default_hides_tagged_cards(self):
        content=(ROOT/'examples'/'fiction'/'index.html').read_text(encoding='utf-8')
        self.assertEqual(content.count('data-spoiler="true" hidden'),2)
    def test_release_checker_rejects_unlisted_and_sensitive_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'release-manifest.json').write_text(json.dumps({'files':['release-manifest.json','safe.txt']}),encoding='utf-8')
            (root/'safe.txt').write_text('ghp_'+'x'*36,encoding='utf-8')
            (root/'unlisted.txt').write_text('extra',encoding='utf-8')
            issues,count=inspect(root)
            self.assertTrue(any(x[2]=='github-token' for x in issues))
            self.assertTrue(any(x[2]=='not-in-manifest' for x in issues))

if __name__=='__main__':unittest.main()
