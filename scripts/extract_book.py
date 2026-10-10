"""Extract local book content without executing it. Does not summarize a book."""
import argparse, hashlib, json, posixpath, re, zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

IMAGE_TYPES={'.png','.jpg','.jpeg','.gif','.webp'}

class BoundedZip:
    """Check ZIP metadata and enforce actual decompression budgets before use."""
    MAX_MEMBERS=10000
    MAX_MEMBER_BYTES=64*1024*1024
    MAX_TOTAL_BYTES=256*1024*1024
    def __init__(self, archive):
        self.archive=archive;self.bytes_read=0
        entries=archive.infolist()
        if len(entries)>self.MAX_MEMBERS:raise ValueError('归档条目数超过安全上限。')
        if any(x.file_size>self.MAX_MEMBER_BYTES for x in entries):raise ValueError('归档单条目解压大小超过64 MiB上限。')
        if sum(x.file_size for x in entries)>self.MAX_TOTAL_BYTES:raise ValueError('归档总解压大小超过256 MiB上限。')
    def namelist(self):return self.archive.namelist()
    def read(self, name):
        chunks=[];size=0
        with self.archive.open(name) as member:
            while True:
                remaining=min(self.MAX_MEMBER_BYTES-size,self.MAX_TOTAL_BYTES-self.bytes_read)
                chunk=member.read(min(65536,remaining+1))
                if not chunk:break
                size+=len(chunk);self.bytes_read+=len(chunk)
                if size>self.MAX_MEMBER_BYTES or self.bytes_read>self.MAX_TOTAL_BYTES:
                    raise ValueError('归档实际解压读取量超过安全上限。')
                chunks.append(chunk)
        return b''.join(chunks)

def file_digest(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

class Blocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.blocks=[];self.images=[];self.skip=0;self.tag=None;self.parts=[];self.fallback=[]
    def flush(self):
        text=re.sub(r'\s+',' ',''.join(self.parts)).strip()
        if text:self.blocks.append((self.tag or 'p',text))
        self.tag=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1;return
        if self.skip:return
        attrs=dict(attrs)
        if tag=='img' and attrs.get('src'):self.images.append(attrs['src'])
        if tag in ('h1','h2','h3','h4','h5','h6','p','li','blockquote','pre','tr','dt','dd'):
            if self.tag is None:self.tag=tag
            elif tag in ('p','h1','h2','h3') and self.tag not in ('li','blockquote','tr'):self.flush();self.tag=tag
        if tag in ('br','td','th') and self.tag:self.parts.append(' | ' if tag in ('td','th') else ' ')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1);return
        if self.skip:return
        if tag==self.tag:self.flush()
    def handle_data(self,data):
        if self.skip:return
        self.fallback.append(data)
        if self.tag:self.parts.append(data)
    def finish(self):
        self.flush()
        if not self.blocks:
            text=re.sub(r'\s+',' ',''.join(self.fallback)).strip()
            if text:self.blocks=[('p',text)]
        return self.blocks

def decode(raw):
    encodings=['utf-8-sig']
    if raw.startswith((b'\xff\xfe',b'\xfe\xff')):encodings.insert(0,'utf-16')
    encodings+=['gb18030']
    for enc in encodings:
        try:return raw.decode(enc),enc
        except UnicodeDecodeError:pass
    raise ValueError('不能可靠识别文字编码；请先确认或转换输入编码。')

def archive_path(name):
    name=posixpath.normpath(name.replace('\\','/'))
    if name.startswith(('../','/')) or name=='..':raise ValueError('归档内存在不安全路径：'+name)
    return name

def extract(source,out):
    source=source.resolve();out.mkdir(parents=True,exist_ok=True)
    segments=[];images=[];warnings=[];metadata={'title':source.stem,'author':''}
    def add(locator,blocks,titles=None,image_paths=None):
        sid=f'S{len(segments)+1:04}'
        paragraphs=[dict(id=f'P{i:04}',kind=kind,text=text) for i,(kind,text) in enumerate(blocks,1) if text.strip()]
        segments.append(dict(id=sid,locator=locator,titles=titles or [],paragraphs=paragraphs,images=image_paths or []))
    def save_image(raw,suffix,original):
        if suffix.lower() not in IMAGE_TYPES:return None
        target=out/'images'/f'image-{len(images)+1:04}{suffix.lower()}';target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
        rel=target.relative_to(out).as_posix();images.append(dict(path=rel,original=original,sha256=hashlib.sha256(raw).hexdigest()));return rel
    ext=source.suffix.lower()
    if ext=='.epub':
        with zipfile.ZipFile(source) as archive:
            z=BoundedZip(archive)
            container=ET.fromstring(z.read('META-INF/container.xml'));opf_name=archive_path(container.find('.//{*}rootfile').get('full-path'));base=posixpath.dirname(opf_name)
            opf=ET.fromstring(z.read(opf_name));manifest={x.get('id'):x for x in opf.find('{*}manifest')}
            for el in opf.find('{*}metadata'):
                tag=el.tag.split('}')[-1]
                if tag in ('title','creator','publisher','language','date'):metadata['author' if tag=='creator' else tag]=''.join(el.itertext()).strip()
            labels={};image_map={}
            for item in manifest.values():
                name=archive_path(posixpath.join(base,item.get('href').split('#')[0]))
                media=item.get('media-type','')
                if media.startswith('image/'):
                    rel=save_image(z.read(name),Path(name).suffix,name)
                    if rel:image_map[name]=rel
                    else:warnings.append('未自动嵌入图像格式：'+name)
                if media=='application/x-dtbncx+xml':
                    toc=ET.fromstring(z.read(name))
                    for point in toc.findall('.//{*}navPoint'):
                        href=point.find('{*}content').get('src').split('#')[0];key=archive_path(posixpath.join(posixpath.dirname(name),href))
                        title=''.join(point.find('{*}navLabel').itertext()).strip();labels.setdefault(key,[]).append(title)
                if 'nav' in item.get('properties','').split():
                    tree=ET.fromstring(z.read(name))
                    for a in tree.findall('.//{*}a'):
                        href=a.get('href','').split('#')[0]
                        if href and '://' not in href:
                            key=archive_path(posixpath.join(posixpath.dirname(name),href));labels.setdefault(key,[]).append(''.join(a.itertext()).strip())
            for ref in opf.find('{*}spine'):
                item=manifest[ref.get('idref')];name=archive_path(posixpath.join(base,item.get('href').split('#')[0]))
                text,_=decode(z.read(name));parser=Blocks();parser.feed(text);blocks=parser.finish();used=[]
                for img in parser.images:
                    if '://' in img or img.startswith('data:'):warnings.append('未加载外部/内联源图像：'+name);continue
                    img=archive_path(posixpath.join(posixpath.dirname(name),img.split('#')[0]));rel=image_map.get(img)
                    if rel:used.append(rel)
                add({'format':'epub','path':name},blocks,list(dict.fromkeys(labels.get(name,[]))),list(dict.fromkeys(used)))
    elif ext=='.docx':
        ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        with zipfile.ZipFile(source) as archive:
            z=BoundedZip(archive)
            tree=ET.fromstring(z.read('word/document.xml'));blocks=[]
            for child in tree.find(ns+'body'):
                if child.tag==ns+'p':
                    text=''.join(x.text or '' for x in child.iter(ns+'t'));style=child.find('.//'+ns+'pStyle');kind='h2' if style is not None and 'heading' in style.get(ns+'val','').lower() else 'p'
                    if text.strip():blocks.append((kind,text.strip()))
                elif child.tag==ns+'tbl':
                    for row in child.findall(ns+'tr'):
                        cells=[' '.join(x.text or '' for x in cell.iter(ns+'t')) for cell in row.findall(ns+'tc')];blocks.append(('table-row',' | '.join(cells)))
            for name in z.namelist():
                if name.startswith('word/media/'):save_image(z.read(name),Path(name).suffix,name)
            add({'format':'docx','path':'word/document.xml'},blocks)
            warnings.append('DOCX基础提取不保证文本框、图表、公式、批注或图片位置完整；请渲染回查。')
    elif ext=='.pdf':
        try:
            import fitz
            with fitz.open(source) as doc:
                if doc.needs_pass:raise ValueError('PDF需要密码，尚未读取。')
                for i,page in enumerate(doc):
                    text=page.get_text('text',sort=True);blocks=[('p',p.strip()) for p in re.split(r'\n\s*\n',text) if p.strip()]
                    add({'format':'pdf','page':i+1,'page_index':i},blocks)
                    if len(text.strip())<30:warnings.append(f'PDF物理页{i+1}文字稀少或无文本层，需判断是否OCR/空页。')
        except ImportError:
            try:import pdfplumber
            except ImportError:raise RuntimeError('需要环境现有的PyMuPDF或pdfplumber；请定位依赖或采用PDF阅读工具。')
            with pdfplumber.open(source) as doc:
                for i,page in enumerate(doc.pages):
                    text=page.extract_text() or '';add({'format':'pdf','page':i+1,'page_index':i},[('p',p.strip()) for p in text.split('\n') if p.strip()])
                    if len(text.strip())<30:warnings.append(f'PDF物理页{i+1}需检查OCR。')
        warnings.append('PDF基础提取未恢复嵌图、多栏、脚注或复杂表格；请抽查版面并按需补充图像。')
    elif ext in ('.html','.htm'):
        text,enc=decode(source.read_bytes());parser=Blocks();parser.feed(text);blocks=parser.finish();add({'format':'html','path':source.name},blocks)
        if parser.images:warnings.append('HTML中的图像尚未归档，需检查真实可用图像并嵌入。')
        metadata['encoding']=enc
    elif ext in ('.txt','.md','.markdown'):
        text,enc=decode(source.read_bytes());metadata['encoding']=enc;blocks=[];title=[]
        for p in re.split(r'\n\s*\n',text):
            lines=p.strip().splitlines()
            for line_index,line in enumerate(lines):
                heading=bool(re.match(r'^#{1,6}\s+|^第[零〇一二三四五六七八九十百千万\d]+[章节卷部回幕]',line.strip()))
                if heading:
                    if blocks:add({'format':ext.lstrip('.'),'path':source.name},blocks,title);blocks=[]
                    title=[re.sub(r'^#+\s*','',line.strip())];blocks.append(('h2',title[0]))
                elif line.strip():
                    if blocks and blocks[-1][0]=='p':blocks[-1]=('p',blocks[-1][1]+'\n'+line.strip())
                    else:blocks.append(('p',line.strip()))
            if blocks and blocks[-1][0]=='p':blocks.append(('separator',''))
        if blocks:add({'format':ext.lstrip('.'),'path':source.name},blocks,title)
    else:raise ValueError('不支持此格式；请先用可靠工具转换或按source-formats参考读取。')
    if not any(s['paragraphs'] for s in segments):raise ValueError('未提取到可读正文，不能生成全书梳理。')
    data=dict(metadata=metadata,source_path=source.name,sha256=file_digest(source),warnings=warnings,segments=segments,images=images)
    (out/'source.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    texts=out/'segments';texts.mkdir(exist_ok=True)
    for s in segments:
        (texts/(s['id']+'.txt')).write_text(s['id']+' | '+json.dumps(s['locator'],ensure_ascii=False)+'\n'+'\n'.join('['+p['id']+'] '+p['text'] for p in s['paragraphs']),encoding='utf-8')
    print(json.dumps(dict(output=str(out/'source.json'),segments=len(segments),paragraphs=sum(len(s['paragraphs']) for s in segments),warnings=warnings),ensure_ascii=False))
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();extract(args.source,args.out)
