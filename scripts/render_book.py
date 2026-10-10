"""Render curated knowledge JSON as a self-contained, genre-aware HTML artifact."""
import argparse, base64, hashlib, html, json, mimetypes
from pathlib import Path
from validate_book import check

e=lambda x:html.escape(str(x),quote=True)
ORIGINS={'source':'原书内容','interpretation':'整理者解读','editorial':'整理者补充'}
def render(source_path,knowledge_path,out):
    source=json.loads(source_path.read_text(encoding='utf-8'));book=json.loads(knowledge_path.read_text(encoding='utf-8'))
    report=check(source,book,knowledge_path.parent)
    if not report['passed']:raise ValueError('结构错误：'+'；'.join(report['errors']))
    assets=Path(__file__).resolve().parents[1]/'assets';css=(assets/'style.css').read_text(encoding='utf-8');js=(assets/'app.js').read_text(encoding='utf-8')
    units=book['units'];segments={s['id']:s for s in source['segments']};groups={g['id']:g['title'] for g in book['groups']}
    mode_label={'nonfiction':'知识与非虚构','fiction':'小说与叙事','mixed':'混合体裁'}[book['mode']]
    dom_ids={u['id']:f'book-unit-{i}' for i,u in enumerate(units,1)};cards=[];figures=0
    for number,u in enumerate(units,1):
        pts=[];refs=set()
        for p in u['points']:
            location=[]
            for r in p.get('refs',[]):
                refs.update((r['segment'],pid) for pid in r['paragraphs']);location.append(r['segment']+' / '+', '.join(r['paragraphs']))
            pts.append(f'<li>{e(p["text"])}<small class="ref">{e(ORIGINS[p.get("origin","source")])}'+(' · '+e('；'.join(location)) if location else '')+'</small></li>')
        tables=[]
        for t in u.get('tables',[]):
            heads=''.join(f'<th scope="col">{e(h)}</th>' for h in t['headers']);rows=''.join('<tr>'+''.join(f'<th scope="row">{e(v)}</th>' if i==0 else f'<td>{e(v)}</td>' for i,v in enumerate(row))+'</tr>' for row in t['rows'])
            tables.append(f'<section class="model"><h3>{e(t["title"])}</h3><small class="ref">{e(ORIGINS[t.get("origin","editorial")])}</small><div class="table-scroll" tabindex="0" aria-label="{e(t["title"])}"><table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table></div></section>')
        sidebar=[]
        if u.get('exercise'):
            ex=u['exercise'];sidebar.append(f'<div class="practice"><div class="eyebrow">整理者补充</div><h3>{e(ex["title"])}</h3><ol>'+''.join(f'<li>{e(step)}</li>' for step in ex['steps'])+'</ol></div>')
        for f in u.get('figures',[]):
            path=(knowledge_path.parent/f['path']).resolve();raw=path.read_bytes();uri='data:'+mimetypes.guess_type(path)[0]+';base64,'+base64.b64encode(raw).decode();figures+=1
            for r in f.get('refs',[]):refs.update((r['segment'],pid) for pid in r['paragraphs'])
            sidebar.append(f'<figure><figcaption><span class="badge">{e(ORIGINS[f.get("origin","source")])}</span> {e(f["alt"])}</figcaption><button class="image-button" type="button" aria-label="放大：{e(f["alt"])}"><img src="{uri}" alt="{e(f["alt"])}" loading="lazy"></button><p>{e(f["caption"])}</p><small>点击放大</small></figure>')
        excerpts=[]
        for sid,pid in sorted(refs):
            s=segments[sid];p=next(p for p in s['paragraphs'] if p['id']==pid);text=p['text'];locator=json.dumps(s['locator'],ensure_ascii=False)
            excerpts.append(f'<p><b>{e(sid)} / {e(pid)}</b> <small>{e(locator)}</small><br>{e(text[:180])}{"……" if len(text)>180 else ""}</p>')
        note=('<p class="note">'+e(u['note'])+'</p>') if u.get('note') else ''
        sources=f'<details class="source"><summary>来源定位与短摘录 <span>{len(refs)}个段落</span></summary><div class="source-body">{note}<p class="source-meta">段落号是本项目提取编号，不自动等于印刷页码。解读与辅助练习由整理者提供；来源摘录用于回查。</p>{"".join(excerpts)}</div></details>'
        quiz=''
        if u.get('question'):
            q=u['question'];quiz=f'<section class="quiz"><div class="quiz-label">想一想 <small>整理者补充 · 参考要点并非唯一读法</small></div><p>{e(q["prompt"])}</p><details class="answer"><summary>查看参考回应</summary><p>{e(q["answer"])}</p></details></section>'
        grid=f'<div class="card-grid{" text-only" if not sidebar else ""}"><div><h3>内容梳理</h3><ul class="points">{"".join(pts)}</ul>{"".join(tables)}</div>'+(f'<aside>{"".join(sidebar)}</aside>' if sidebar else '')+'</div>'
        cards.append(f'<article class="card" id="{dom_ids[u["id"]]}" data-unit="{e(u["id"])}" data-group="{e(u["group"])}" data-spoiler="{str(u.get("spoiler",False)).lower()}"><header class="card-header"><div class="number">{number:02}</div><div><div class="eyebrow">{e(groups[u["group"]])} · {e(u.get("kind","内容梳理"))}</div><h2>{e(u["title"])}</h2></div><button class="mark" type="button" aria-pressed="false" aria-label="标记已读：{e(u["title"])}">标记已读</button></header><p class="lead">{e(u["lead"])}</p>{grid}{quiz}{sources}</article>')
    nav=[]
    for g in book['groups']:
        nav.append(f'<div class="nav-group">{e(g["title"])}</div>')
        nav.extend(f'<a class="chapter-link" data-unit="{e(u["id"])}" href="#{dom_ids[u["id"]]}"><span>{i:02}</span>{e(u["title"])}</a>' for i,u in enumerate(units,1) if u['group']==g['id'])
    filters=''.join(f'<button class="group-filter" type="button" data-group="{e(g["id"])}" aria-pressed="false">{e(g["title"])}</button>' for g in book['groups'])
    spoiler_control=''
    if any(u.get('spoiler') for u in units):spoiler_control='<div class="spoiler-control"><label><input id="show-spoilers" type="checkbox"> 显示含剧透内容</label><p>完整梳理包含关键情节与结局。关闭时隐藏标记为剧透的单元；标题与导读仍由整理者保证无剧透。</p></div>'
    work=''
    if book.get('routes'):
        route_label=book.get('route_label','阅读问题检索');buttons=''.join(f'<button class="scenario" type="button" data-index="{i}">{e(r["title"])}</button>' for i,r in enumerate(book['routes']))
        work=f'<section class="work" id="work"><div class="section-head"><h2>{e(route_label)}</h2><span class="badge">本地关键词匹配</span></div><p>查找本书相关单元。推荐仅在本页匹配，不自动生成新答案。</p><form id="work-form"><label class="sr-only" for="work-question">输入阅读问题</label><input id="work-question" type="search" maxlength="300" placeholder="输入问题或关键词"><button type="submit">查找相关内容</button><button id="work-clear" type="button">清空</button></form><details class="scenario-list"><summary>常见问题</summary><div class="scenario-buttons">{buttons}</div></details><div id="work-output" hidden><p id="work-status" role="status" aria-live="polite"></p><div id="work-results"></div></div></section>'
    toolbox=''
    if book.get('templates'):
        templates=''.join(f'<details class="template"><summary>{e(t["title"])}</summary><p>{e(t.get("description","整理者补充记录模板"))}</p><label for="draft-{i}">{e(t["title"])}填写区</label><textarea id="draft-{i}" data-title="{e(t["title"])}" spellcheck="false">{e(t["text"])}</textarea><button class="copy" type="button" data-target="draft-{i}">复制</button></details>' for i,t in enumerate(book['templates'],1))
        toolbox=f'<section class="toolbox" id="toolbox"><h2>阅读与练习记录</h2><p>整理者补充。编辑内容只在当前页面保留，关闭前可主动导出。</p>{templates}<div class="tool-actions"><button id="export-drafts" type="button">导出全部草稿</button></div><p id="tool-status" role="status" aria-live="polite"></p></section>'
    quicklinks=(('<a href="#work">'+e(book.get('route_label','阅读问题检索'))+'</a>') if work else '')+('<a href="#toolbox">阅读与练习记录</a>' if toolbox else '')
    scope=book['coverage']['scope'];scope_label='完整目标范围' if scope=='full' else '部分范围'
    coverage_rows=''.join(f'<li>{e(c["label"])} · {e({"read":"已读整理","unread":"未读","excluded":"排除"}[c["status"]])} · {e(", ".join(c["segments"]))} {e(c.get("reason",""))}</li>' for c in book['coverage']['items'])
    warning_html=''.join(f'<li>{e(w)}</li>' for w in source.get('warnings',[]))
    payload=json.dumps(dict(book=book,dom_ids=dom_ids,total=len(units),storage_key='book-html-'+hashlib.sha256((source['sha256']+book['title']).encode()).hexdigest()[:20]),ensure_ascii=False).replace('<','\\u003c')
    artifact=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(book['title'])} · 读书讲义</title><style>{css}</style></head><body><a class="skip" href="#main">跳到正文</a><header class="topbar"><a class="brand" href="#top">读书讲义 <span>{e(mode_label)}</span></a><button id="menu" type="button" aria-controls="sidebar" aria-expanded="false">目录</button><div class="search-box"><label for="search" class="sr-only">搜索内容</label><input id="search" type="search" placeholder="搜索本书内容"><button id="clear" type="button" aria-label="清空搜索">×</button></div><button id="print" type="button">打印 / 存为PDF</button></header><div class="layout"><nav class="sidebar" id="sidebar" aria-label="阅读目录"><div class="sidebar-top">{quicklinks}<p id="progress" aria-live="polite"></p><button id="reset-progress" type="button">重置已读</button></div>{''.join(nav)}</nav><main id="main"><section class="hero" id="top"><div class="eyebrow">BOOK NOTES / OFFLINE</div><h1>{e(book['title'])}</h1><p>{e(book.get('subtitle','按原书脉络阅读，带着问题重新思考。'))}</p><div class="hero-meta"><span>{len(book['groups'])}组</span><span>{len(units)}个阅读单元</span><span>{figures}幅图像</span><span>{e(scope_label)}</span></div><div class="author">{e(book.get('author','作者未确认'))}</div></section><section class="overview"><h2>阅读导览</h2><p>{e(book['summary'])}</p>{spoiler_control}<details class="about"><summary>来源、范围与整理说明</summary><p>原书概括、整理者解读和新增辅助分别标明。脚本仅完成渲染与引用检查，不能证明解释唯一正确。源书制度与数据保持原书语境，不代表今日事实。</p><p>覆盖声明：{e(scope_label)}</p><ul>{coverage_rows}</ul>{('<p>提取注意事项：</p><ul>'+warning_html+'</ul>') if warning_html else ''}<p>页面无需联网。来源路径及段落号可在单元底部回查。已读标记在浏览器允许时保存在本机；练习草稿需主动导出。</p></details></section>{work}<section class="filter-panel" aria-label="分组筛选"><button class="group-filter selected" type="button" data-group="all" aria-pressed="true">全部</button>{filters}<div id="search-status" role="status" aria-live="polite"></div></section><div id="empty" hidden>没有匹配的可见内容。可清空搜索、选择全部；需要阅读完整情节时请开启剧透。</div><div id="cards">{''.join(cards)}</div>{toolbox}<footer><p>依据用户提供的书籍整理。保留原文语境，理解与讨论可以存在多种读法。</p></footer></main></div><dialog id="image-dialog"><div class="dialog-top"><strong id="image-title">图像</strong><button id="image-close" type="button">关闭</button></div><div class="dialog-scroll"><img id="big-image" alt=""></div></dialog><button id="back-top" type="button" aria-label="返回页首">↑</button><noscript><div class="no-script">需要启用JavaScript才能检索和切换剧透；标记为剧透的单元按初始设置隐藏。</div></noscript><script id="book-data" type="application/json">{payload}</script><script>{js}</script></body></html>'''
    if book.get('spoiler_default','hide')!='show':artifact=artifact.replace('data-spoiler="true"','data-spoiler="true" hidden')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(artifact,encoding='utf-8')
    print(json.dumps(dict(output=str(out),units=len(units),images=figures,sha256=hashlib.sha256(out.read_bytes()).hexdigest()),ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--knowledge',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();render(a.source,a.knowledge,a.out)
