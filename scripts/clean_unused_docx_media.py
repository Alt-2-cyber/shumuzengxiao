from __future__ import annotations

import posixpath
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def rels_source_part(rels_name: str) -> str:
    # word/_rels/document.xml.rels -> word/document.xml
    directory, filename = posixpath.split(rels_name)
    if not directory.endswith("_rels") or not filename.endswith(".rels"):
        raise ValueError(rels_name)
    base_dir = posixpath.dirname(directory)
    source = filename[:-5]
    return posixpath.join(base_dir, source) if base_dir else source


def resolve_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def rel_ids_used(xml_bytes: bytes) -> set[str]:
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return set()
    used: set[str] = set()
    for elem in root.iter():
        for attr_name, value in elem.attrib.items():
            if attr_name == f"{{{R_NS}}}embed" or attr_name == f"{{{R_NS}}}id" or attr_name == f"{{{R_NS}}}link":
                used.add(value)
    return used


def clean_docx_media(input_path: Path, output_path: Path) -> None:
    with ZipFile(input_path, "r") as zin:
        original_names = zin.namelist()
        data = {name: zin.read(name) for name in original_names}

    image_targets_to_keep: set[str] = set()
    removed_rels: dict[str, int] = {}

    for name in list(original_names):
        if not name.endswith(".rels") or "/_rels/" not in name:
            continue
        source_part = rels_source_part(name)
        if source_part not in data:
            continue
        used_ids = rel_ids_used(data[source_part])
        try:
            root = etree.fromstring(data[name])
        except etree.XMLSyntaxError:
            continue
        removed = 0
        for rel in list(root):
            if rel.tag != f"{{{REL_NS}}}Relationship":
                continue
            rel_type = rel.get("Type")
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if rel_type == IMAGE_REL and target:
                full_target = resolve_target(source_part, target)
                if rel_id in used_ids:
                    image_targets_to_keep.add(full_target)
                else:
                    root.remove(rel)
                    removed += 1
        if removed:
            removed_rels[name] = removed
            data[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=False)

    media_removed = 0
    filtered_names: list[str] = []
    for name in original_names:
        if name.startswith("word/media/") and name not in image_targets_to_keep:
            media_removed += 1
            continue
        filtered_names.append(name)

    with ZipFile(output_path, "w", ZIP_DEFLATED) as zout:
        for name in filtered_names:
            zout.writestr(name, data[name])

    print(f"removed_media={media_removed}")
    print(f"removed_image_relationships={sum(removed_rels.values())}")


if __name__ == "__main__":
    src = Path(r"D:\table\shumuzengxiao\outputs\muyunzhishe_challenge_cup_business_plan_strict_template.docx")
    dst = Path(r"D:\table\shumuzengxiao\outputs\muyunzhishe_challenge_cup_business_plan_strict_template_clean.docx")
    clean_docx_media(src, dst)
    cn = Path(r"D:\table\shumuzengxiao\outputs\牧云智舍-挑战杯商业计划书-严格模板版.docx")
    shutil.copyfile(dst, cn)
