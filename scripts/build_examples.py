"""Rebuild only the two repository-owned original examples."""
from pathlib import Path
from extract_book import extract
from render_book import render
from validate_book import Audit

ROOT=Path(__file__).resolve().parents[1]

def build():
    for genre in ('nonfiction','fiction'):
        folder=ROOT/'examples'/genre
        extract(folder/'original.md',folder/'source')
        render(folder/'source'/'source.json',folder/'knowledge.json',folder/'index.html')
        generated=[folder/'source'/'source.json',folder/'index.html',*(folder/'source'/'segments').glob('*.txt')]
        for path in generated:path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
        audit=Audit();audit.feed((folder/'index.html').read_text(encoding='utf-8'))
        if audit.external or len(audit.ids)!=len(set(audit.ids)) or any(x not in audit.ids for x in audit.links):
            raise ValueError('Example failed offline/link checks: '+genre)

if __name__=='__main__':build()
