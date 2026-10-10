"""Validate source pointers and structural coverage, not literary/semantic accuracy."""
import argparse, json
from html.parser import HTMLParser
from pathlib import Path

def check(source,knowledge,base):
    errors=[];warnings=list(source.get('warnings',[]));segments={s['id']:s for s in source['segments']}
    if len(segments)!=len(source['segments']):errors.append('重复来源单元ID')
    for s in source['segments']:
        ids=[p['id'] for p in s['paragraphs']]
        if len(ids)!=len(set(ids)):errors.append('重复段落ID：'+s['id'])
    def refs_valid(refs,label):
        if not refs:errors.append('缺少来源：'+label);return
        for ref in refs:
            sid=ref.get('segment');s=segments.get(sid)
            if not s:errors.append('不存在的来源单元：'+str(sid));continue
            available={p['id'] for p in s['paragraphs']}
            if not ref.get('paragraphs'):errors.append('未指定来源段落：'+label)
            for p in ref.get('paragraphs',[]):
                if p not in available:errors.append(f'不存在的段落：{sid}/{p}')
    if knowledge.get('mode') not in ('fiction','nonfiction','mixed'):errors.append('mode必须是fiction/nonfiction/mixed')
    if not knowledge.get('title') or not knowledge.get('summary'):errors.append('缺少书名或导读')
    group_ids=[g['id'] for g in knowledge.get('groups',[])]
    if len(group_ids)!=len(set(group_ids)):errors.append('重复分组ID')
    units=knowledge.get('units',[]);ids=[u['id'] for u in units]
    if not units:errors.append('没有整理单元')
    if len(ids)!=len(set(ids)):errors.append('重复整理单元ID')
    for u in units:
        if u.get('group') not in group_ids:errors.append('未知分组：'+u['id'])
        if not u.get('title') or not u.get('lead'):errors.append('缺少单元名称或概括：'+u['id'])
        if not isinstance(u.get('spoiler',False),bool):errors.append('spoiler不是布尔值：'+u['id'])
        points=u.get('points',[])
        if not points:errors.append('没有正文要点：'+u['id'])
        if not any(p.get('refs') for p in points):errors.append('单元没有任何有来源的要点：'+u['id'])
        for p in points:
            origin=p.get('origin','source')
            if origin not in ('source','interpretation','editorial'):errors.append('未知origin：'+u['id'])
            if not p.get('text'):errors.append('空正文要点：'+u['id'])
            if origin!='editorial' or p.get('refs'):refs_valid(p.get('refs'),u['id'])
        for t in u.get('tables',[]):
            if not t.get('headers') or not t.get('rows'):errors.append('空表格：'+u['id'])
            if any(len(r)!=len(t.get('headers',[])) for r in t.get('rows',[])):errors.append('表格列数不同：'+u['id'])
        for f in u.get('figures',[]):
            path=(base/f['path']).resolve()
            if not path.is_file():errors.append('图像不存在：'+str(path))
            if path.suffix.lower() not in ('.png','.jpg','.jpeg','.gif','.webp'):errors.append('渲染器不支持图像格式：'+str(path))
            if not f.get('alt') or not f.get('caption'):errors.append('缺少图像说明：'+u['id'])
            if f.get('origin','source')!='editorial':refs_valid(f.get('refs'),u['id']+'图像')
    for route in knowledge.get('routes',[]):
        if not route.get('keywords') or not route.get('units'):errors.append('检索路由缺少关键词或单元')
        for uid in route.get('units',[]):
            if uid not in ids:errors.append('检索路由指向未知单元：'+uid)
    coverage=knowledge.get('coverage',{});items=coverage.get('items',[]);covered=set()
    if coverage.get('scope') not in ('full','partial'):errors.append('覆盖声明应为full或partial')
    for item in items:
        status=item.get('status')
        if status not in ('read','unread','excluded'):errors.append('未知覆盖状态')
        if status in ('excluded','unread') and not item.get('reason'):errors.append('排除/未读范围缺少原因')
        for sid in item.get('segments',[]):
            if sid not in segments:errors.append('覆盖表指向未知来源：'+sid)
            covered.add(sid)
            if status=='read' and sid in segments and not segments[sid]['paragraphs']:errors.append('空文本单元不能声明已读：'+sid)
        if coverage.get('scope')=='full' and status=='unread':errors.append('有未读内容却声明完整覆盖')
    missing=set(segments)-covered
    if missing:errors.append('覆盖表遗漏提取单元：'+', '.join(sorted(missing)))
    if knowledge.get('mode')=='fiction' and not any(u.get('spoiler') for u in units):warnings.append('小说没有剧透标记，请人工检查是否确实仅包含无剧透内容。')
    if warnings:warnings.append('源文件警告需人工处理；结构检查不确认文本含义、图像读序或阅读覆盖的真实性。')
    return dict(passed=not errors,errors=errors,warnings=warnings,units=len(units),groups=len(group_ids),source_segments=len(segments),coverage_scope=coverage.get('scope'))

class Audit(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.links=[];self.external=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='a' and attrs.get('href','').startswith('#'):self.links.append(attrs['href'][1:])
        if tag in ('img','script','link','iframe'):
            url=attrs.get('src',attrs.get('href',''))
            if url and not url.startswith(('data:','#')):self.external.append(url)

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--knowledge',required=True,type=Path);p.add_argument('--html',type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
    s=json.loads(a.source.read_text(encoding='utf-8'));k=json.loads(a.knowledge.read_text(encoding='utf-8'));report=check(s,k,a.knowledge.parent)
    if a.html:
        audit=Audit();audit.feed(a.html.read_text(encoding='utf-8'))
        if len(audit.ids)!=len(set(audit.ids)):report['errors'].append('HTML重复ID')
        if any(link not in audit.ids for link in audit.links):report['errors'].append('HTML存在无效内部链接')
        if audit.external:report['errors'].append('HTML存在非内嵌资源：'+str(audit.external))
        report['passed']=not report['errors']
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
