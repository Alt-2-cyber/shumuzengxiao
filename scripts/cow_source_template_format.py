from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET
from PIL import ImageFont

REFERENCE = Path(r'D:\Users\q4984\xwechat_files\wxid_rt7txr6f1vcl22_d661\msg\attach\ab6b1a8712ca2561dd0c8acc4e68ce59\2026-10\Rec\51ab2f3c6e5ad6e3\F\1\代码模板(1)(2).docx')
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
FONT = ImageFont.truetype(r'C:\Windows\Fonts\Deng.ttf', 120)


def element(name, **attributes):
    node = ET.Element(f'{{{W}}}{name}')
    for key, value in attributes.items():
        node.set(f'{{{W}}}{key}', str(value))
    return node


def serialize(root):
    return ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)


def write_source_document(name, output: Path, pages, reference=REFERENCE):
    with ZipFile(reference) as archive:
        parts = {item.filename: archive.read(item.filename) for item in archive.infolist()}
        infos = archive.infolist()
    document = ET.fromstring(parts['word/document.xml'])
    body = document.find('w:body', NS)
    section = deepcopy(body.find('w:sectPr', NS))
    paragraph_properties = deepcopy(body.find('w:p/w:pPr', NS))
    page = section.find('w:pgSz', NS)
    margins = section.find('w:pgMar', NS)
    available_points = (int(page.get(f'{{{W}}}w')) - int(margins.get(f'{{{W}}}left')) -
                        int(margins.get(f'{{{W}}}right'))) / 20 - 2
    for node in list(body):
        body.remove(node)
    for page_index, rows in enumerate(pages):
        for row_index, row in enumerate(rows):
            paragraph = element('p')
            properties = deepcopy(paragraph_properties)
            properties.append(element('jc', val='left'))
            if page_index > 0 and row_index == 0:
                properties.insert(0, element('pageBreakBefore'))
            paragraph.append(properties)
            content = row['text'].expandtabs(2)
            run = element('r')
            expected_width = FONT.getlength(content) / 10
            # Word reserves half-em advances for leading spaces in this template.
            leading_spaces = len(content) - len(content.lstrip(' '))
            expected_width += leading_spaces * (6 - FONT.getlength(' ') / 10)
            ratio = min(100, math.floor(available_points / max(expected_width, 1) * 90))
            if ratio < 100:
                rpr = element('rPr')
                rpr.append(element('w', val=max(1, ratio)))
                run.append(rpr)
            text = element('t')
            text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            text.text = content
            run.append(text)
            paragraph.append(run)
            body.append(paragraph)
    body.append(section)
    parts['word/document.xml'] = serialize(document)
    for part in ('word/header1.xml', 'word/header2.xml'):
        header = ET.fromstring(parts[part])
        for paragraph in header.findall('.//w:p', NS):
            texts = paragraph.findall('.//w:t', NS)
            if any(node.text and 'Instagram' in node.text for node in texts):
                for index, node in enumerate(texts):
                    node.text = name + ' V1.0' if index == 0 else ''
        parts[part] = serialize(header)
    core = ET.fromstring(parts['docProps/core.xml'])
    for node in core:
        local = ET.QName(node).localname
        if local in ('creator', 'lastModifiedBy', 'description', 'subject'):
            node.text = ''
        elif local == 'title':
            node.text = name + ' V1.0'
    parts['docProps/core.xml'] = serialize(core)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w') as archive:
        for info in infos:
            archive.writestr(info, parts[info.filename])
    return output
