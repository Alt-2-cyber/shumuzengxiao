# -*- coding: utf-8 -*-
from pathlib import Path

from build_open_hardware_submission import main
from open_hardware_illustrated_content import enrich_pages

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    main(
        pages=enrich_pages(),
        out_dir=ROOT / "outputs/open_hardware_submission_illustrated_20261026",
        stem="数牧增效-开源智能硬件作品介绍-图文详解版",
        illustrated=True,
    )
