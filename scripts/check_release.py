"""Fail closed on unexpected release files; report rules, never secret values."""
import argparse,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IGNORED={'.git','__pycache__'}
RULES={
    'github-token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b'),
    'provider-secret':re.compile(r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b'),
    'aws-access-key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private-key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential-assignment':re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*["'][A-Za-z0-9_./+=-]{16,}["']'''),
    'personal-windows-directory':re.compile(r'(?i)[A-Z]:[\\/]+(?:Users|Backup|project)[\\/]'),
    'personal-unix-directory':re.compile(r'/(?:home|Users)/[^/\s"\x27]+/'),
    'private-chat-directory':re.compile(r'(?i)(?:xwechat_files|wechat files)[\\/]'),
    'email-address':re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'china-mobile-number':re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'),
}

def inspect(root):
    manifest=json.loads((root/'release-manifest.json').read_text(encoding='utf-8'))
    approved=manifest['files']
    if not approved or len(approved)!=len(set(approved)):raise ValueError('Invalid or duplicate manifest entries')
    for name in approved:
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe manifest path')
    actual=set();issues=[]
    for path in root.rglob('*'):
        rel=path.relative_to(root)
        if any(part in IGNORED for part in rel.parts):continue
        if path.is_symlink():issues.append((rel.as_posix(),0,'symlink'));continue
        if path.is_file():actual.add(rel.as_posix())
    for name in sorted(actual-set(approved)):issues.append((name,0,'not-in-manifest'))
    for name in sorted(set(approved)-actual):issues.append((name,0,'missing-file'))
    for name in sorted(actual&set(approved)):
        path=root/name
        try:content=path.read_text(encoding='utf-8')
        except UnicodeError:issues.append((name,0,'unexpected-binary'));continue
        for number,line in enumerate(content.splitlines(),1):
            for rule,pattern in RULES.items():
                if pattern.search(line):issues.append((name,number,rule))
    return issues,len(actual)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    issues,count=inspect(args.root.resolve())
    print(json.dumps({'passed':not issues,'files':count,'issues':[{'file':p,'line':n,'rule':r} for p,n,r in issues]},ensure_ascii=False))
    return 1 if issues else 0

if __name__=='__main__':raise SystemExit(main())
