from __future__ import annotations

import json

from generate_softcopyright_materials import (
    OUT_DIR,
    build_document_pages,
    collect_source_lines,
    wrap_code_records,
)


def main() -> None:
    records, line_count, _ = collect_source_lines()
    lines = wrap_code_records(records)
    pages = [lines[index:index + 67] for index in range(0, len(lines), 67)]
    if len(pages) < 60:
        raise ValueError("Source has fewer than 60 pages; export the entire source instead.")
    selected = pages[:30] + pages[-30:]
    payload = {
        "softwareName": "牛舍多模态监测平台",
        "version": "V1.0",
        "sourceLineCount": line_count,
        "programPages": selected,
        "documentPages": build_document_pages(),
    }
    output = OUT_DIR / "softcopyright-word-content.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Payload: {output.name}; program={len(selected)}; document={len(payload['documentPages'])}")


if __name__ == "__main__":
    main()
