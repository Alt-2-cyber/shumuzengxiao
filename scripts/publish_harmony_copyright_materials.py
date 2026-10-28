from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import win32com.client

from update_harmony_copyright_materials import NAME, STAGE, TARGET, WORK, sha


def update_indices():
    parent = TARGET.parent
    backups = WORK / '更新前总索引'
    backups.mkdir(exist_ok=True)
    material = json.loads((TARGET / '新版材料清单.json').read_text('utf-8'))
    quality = json.loads((TARGET / '材料质量检查.json').read_text('utf-8'))
    for filename in ['材料生成清单.json', '申请材料质量检查.json', 'Word分页与PDF导出检查.json']:
        path = parent / filename
        if not path.exists():
            continue
        if not (backups / filename).exists():
            shutil.copy2(path, backups / filename)
        items = json.loads(path.read_text('utf-8-sig'))
        if filename == '材料生成清单.json':
            for item in items:
                if item.get('key') == 'hm':
                    item.update(material)
        elif filename == '申请材料质量检查.json':
            for item in items:
                if item.get('software') == NAME:
                    item.update(quality)
                    item['screenshots'] = quality['realScreenshots']
                    item['descriptionCharacters'] = quality['descriptionCharacters']
        else:
            word_report = json.loads((WORK / 'word-export.json').read_text('utf-8-sig'))
            items = [item for item in items if item.get('Software') != NAME]
            for row in word_report:
                row['Software'] = NAME
                row['Pdf'] = str(TARGET / Path(row['Pdf']).name)
                items.append(row)
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), 'utf-8')
    overview = parent / '材料总览.md'
    if overview.exists():
        if not (backups / overview.name).exists():
            shutil.copy2(overview, backups / overview.name)
        lines = overview.read_text('utf-8').splitlines()
        lines = ['| hm | 2390 | 48 | 14 | 10 | 15 |' if line.startswith('| hm |') else line for line in lines]
        overview.write_text('\n'.join(lines) + '\n', 'utf-8')


def main():
    quality = json.loads((STAGE / '材料质量检查.json').read_text('utf-8'))
    for name, expected in quality['files'].items():
        assert sha(STAGE / name) == expected, ('Unverified staging file', name)
    form = TARGET / '申请表模板-待本人填写.docx'
    form_hash = sha(form)
    opened = []
    try:
        wps = win32com.client.GetActiveObject('kwps.Application')
    except Exception:
        wps = None
    if wps is not None:
        for index in range(wps.Documents.Count, 0, -1):
            document = wps.Documents.Item(index)
            path = Path(document.FullName)
            if path.parent.resolve() == TARGET.resolve() and path.name in quality['files']:
                if not document.Saved:
                    raise RuntimeError(f'请先保存正在编辑的文档：{path.name}；新版材料已完成并保留在临时目录。')
                opened.append(path.name)
                document.Close(0)
        time.sleep(0.6)
    retired_root = WORK / ('被替换的旧目录-' + datetime.now().strftime('%H%M%S'))
    retired_root.mkdir()
    for name in ['配图', '源码归档']:
        existing = (TARGET / name).resolve()
        retired = (retired_root / name).resolve()
        assert existing.parent == TARGET.resolve(), 'Directory must remain within the requested material folder'
        assert retired.is_relative_to(WORK.resolve()), 'Retired directory must stay in the task backup area'
        if existing.exists():
            shutil.move(str(existing), str(retired))
        shutil.copytree(STAGE / name, TARGET / name)
    for source in STAGE.iterdir():
        if source.is_file() and not source.name.startswith(('申请表', '~$')):
            shutil.copy2(source, TARGET / source.name)
    assert sha(form) == form_hash, 'Application form changed'
    for name, expected in quality['files'].items():
        assert sha(TARGET / name) == expected, ('Published file mismatch', name)
    update_indices()
    report = dict(folder=str(TARGET), applicationFormSha256=form_hash, applicationFormUnchanged=True,
                  backedUpTo=str(WORK / '更新前材料备份'), sourcePages=48, manualPages=14,
                  screenshots=15, reopenedDocuments=opened,
                  publishedFiles=[source.name for source in STAGE.iterdir() if source.is_file() and not source.name.startswith('申请表')])
    (WORK / 'publication.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    if wps is not None:
        for name in opened:
            wps.Documents.Open(str(TARGET / name))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
