from pathlib import Path
import zipfile

ROOT=Path(r"D:\table\软著申请\牛")
ARCHIVE=ROOT.parent/"牛-三端软著申请材料.zip"

with zipfile.ZipFile(ARCHIVE,"w",zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        relative=path.relative_to(ROOT)
        if relative.parts[0]=="原始参考模板":
            continue
        zf.write(path,relative.as_posix())

with zipfile.ZipFile(ARCHIVE) as zf:
    assert zf.testzip() is None
    print(f"Archive: {ARCHIVE}; entries={len(zf.namelist())}; bytes={ARCHIVE.stat().st_size}")
