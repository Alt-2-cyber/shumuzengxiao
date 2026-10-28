#!/usr/bin/env python3
"""Guard the non-diagnostic public cow-vocalization edge artifact."""

from pathlib import Path


def main() -> None:
    header = Path(__file__).parents[1] / "include" / "cattle_audio_model.h"
    text = header.read_text(encoding="utf-8")
    required = (
        "kEnabled = true",
        'kVersion = "cattle-vocalization-baseline-v2-bedc334739f4"',
        '"cow_vocalization"',
        '"non_cattle_audio"',
        "inline bool isRespiratoryLabel",
        "inline bool isAbnormalVocalizationLabel",
        "inline bool isScreeningLabel",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("acoustic baseline header is not enabled safely: " + ", ".join(missing))
    if 'strcmp(label, "cow_vocalization") == 0' not in text.split("inline bool isScreeningLabel", 1)[-1]:
        raise SystemExit("acoustic baseline must explicitly mark only its event label as screening evidence")
    print("acoustic baseline header contract: PASS")


if __name__ == "__main__":
    main()
