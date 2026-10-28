from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

import win32com.client

from reformat_cow_source_materials import OUT, WORK


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_report_file(path, reports):
    if not path.exists():
        return
    backup = WORK / '修改前备份' / '索引与说明' / path.relative_to(OUT)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(path, backup)
    original = json.loads(path.read_text('utf-8-sig'))
    rows = original if isinstance(original, list) else [original]
    for row in rows:
        name = row.get('software', row.get('name', row.get('Software', '')))
        if name not in reports:
            continue
        report = reports[name]
        row.update({key: value for key, value in report.items() if key not in ('software', 'lineCountsPerPage')})
        files = row.get('files')
        if isinstance(files, dict):
            for filename in list(files):
                if filename.endswith('-源程序.docx'):
                    files[filename] = report['sourceDocxSha256']
                elif filename.endswith('-源程序.pdf'):
                    files[filename] = report['sourcePdfSha256']
    path.write_text(json.dumps(original, ensure_ascii=False, indent=2), 'utf-8')


def main():
    items = json.loads((WORK / '待检查清单.json').read_text('utf-8'))
    reports = {item['software']: item for item in json.loads((WORK / '排版检查.json').read_text('utf-8'))}
    assert len(reports) == len(items) == 3
    targets = {str(Path(item['target']).resolve()).lower(): item for item in items}
    protected = {path: sha(path) for path in OUT.glob('*/*.docx') if not path.name.startswith('~$') and '-源程序' not in path.name}
    reopened = []
    try:
        wps = win32com.client.GetActiveObject('kwps.Application')
    except Exception:
        wps = None
    if wps is not None:
        for index in range(wps.Documents.Count, 0, -1):
            document = wps.Documents.Item(index)
            key = str(Path(document.FullName).resolve()).lower()
            if key not in targets:
                continue
            item = targets[key]
            listing = json.loads((Path(item['target']).parent / '源程序文件与行号清单.json').read_text('utf-8'))
            expected = '\n'.join(row['text'].expandtabs(2) for row in listing['selected'])
            active = re.sub(r'(?m)^\d{5} \| ', '', str(document.Content.Text).replace('\r', '\n').rstrip('\n'))
            assert active == expected, f"当前打开文档有新的源码内容，需要保留后重新排版：{document.Name}"
            if not document.Saved:
                snapshot = WORK / '修改前备份' / item['name'] / 'WPS当前未保存版本.xml'
                snapshot.write_text(str(document.WordOpenXML), 'utf-8')
            reopened.append(str(document.FullName))
            document.Close(0)
        time.sleep(0.5)
    for item in items:
        staged = Path(item['staged'])
        target = Path(item['target'])
        report = reports[item['name']]
        assert sha(staged) == report['sourceDocxSha256']
        assert sha(staged.with_suffix('.pdf')) == report['sourcePdfSha256']
        for suffix in ('.docx', '.pdf'):
            shutil.copy2(staged.with_suffix(suffix), target.with_suffix(suffix))
        (target.parent / '源程序格式检查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        for filename in ['材料质量检查.json', '新版材料清单.json']:
            update_report_file(target.parent / filename, reports)
        explanation = target.parent / '源代码数量及交存说明.md'
        if explanation.exists():
            old = explanation.read_text('utf-8')
            backup = WORK / '修改前备份' / item['name'] / explanation.name
            if not backup.exists():
                shutil.copy2(explanation, backup)
            note = '- 排版按新提供的代码模板：正文不添加数字前缀或竖线，使用Word页边自动行号；字体、页眉与页边距采用模板格式。\n'
            if note not in old:
                explanation.write_text(old + '\n' + note, 'utf-8')
    for filename in ['申请材料质量检查.json', '材料生成清单.json']:
        update_report_file(OUT / filename, reports)
    (OUT / '三份源程序排版检查.json').write_text(json.dumps(list(reports.values()), ensure_ascii=False, indent=2), 'utf-8')
    for path, digest in protected.items():
        assert sha(path) == digest, ('Unrelated document changed', path)
    for item in items:
        target = Path(item['target'])
        assert sha(target) == reports[item['name']]['sourceDocxSha256']
        assert sha(target.with_suffix('.pdf')) == reports[item['name']]['sourcePdfSha256']
    if wps is not None:
        for name in reopened:
            wps.Documents.Open(name)
    print('Published 3 template-formatted DOCX/PDF pairs; manuals and application forms unchanged.')
    print('Reopened:', reopened)


if __name__ == '__main__':
    main()
