# Cross-source-label duplicate review

The automatic preparation quarantined these components before training. A
subsequent visual inspection of `quarantine_contact_sheet.jpg` confirms shared
visual content. This review does not establish a clinical label or animal ID.
Original files and original public directory labels remain unchanged.

| Image group | Original public source paths | Observed duplication |
|---|---|---|
| g-1b1da060003c12a84373 | healthy/IMG_20220906_172625_jpg.rf.0ef9a8dd6b86a8335d7a333c8bc68e5c.jpg; lumpy/IMG_20220906_172625_jpg.rf.2b12cef04d6b2abb57da162489ce1432.jpg | Same scene and animal pose, altered image intensity/color. |
| g-4c0fac7abcca5254833e | foot-and-mouth/img1025.jpg; lumpy/img1025.jpg | Identical image of a lower limb. |
| g-6f8bf9f1f60a905dd763 | healthy/Normal_Skin_588-resized.jpg; lumpy/LS-5_jpg.rf.5dd8e4a818ce76a3888bcdf3004cb140.jpg; lumpy/LS-5_jpg.rf.877b960fd14b38a2fc7eba3d8273a1b4.jpg | Same cattle head and background; resized/rotated/intensity variants. |

All seven images are excluded from train, validation and test. Machine-readable
paths and SHA-256 values are in `quarantine_records.csv` and `manifest.jsonl`.
Connected-component edges and match reasons are in `duplicate_edges.json`.
