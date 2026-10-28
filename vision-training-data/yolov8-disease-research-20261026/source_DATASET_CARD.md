# Kaggle Cattle Diseases Dataset Card

## Source

- Dataset: `devang03mgr/cattle-diseases-datasets`
- URL: https://www.kaggle.com/datasets/devang03mgr/cattle-diseases-datasets
- License reported by Kaggle: `Database: Open Database, Contents: Database Contents`
- Downloaded: 2026-09-18
- ZIP SHA-256: `cee2fc7c03c645e72a5ea5107bc1d6fe5ada55834baa0e1fc4193df36a684e84`

## Inspection

- `foot-and-mouth`: 746 images.
- `healthy`: 1,291 images.
- `lumpy`: 1,207 images.
- Total: 3,244 images.
- No verified animal IDs, farm/date grouping, veterinarian, laboratory result,
  or clinical reference standard was supplied.

## Research Baseline

- Artifact: `D:\table\shumuzengxiao\疾病识别生产落地\研究模型\cattle-disease-multiclass-baseline`
- Version: `cattle-disease-research-797d5d9b4cbc`
- External image-level accuracy: `0.686`.
- External image-level macro-F1: `0.692`.
- Status: `research_only`; no `.mud` file and no MaixCam deployment.

## Safety Decision

The folder name `foot-and-mouth` is not proof of FMD diagnosis. The baseline
is not allowed to emit FMD positive/negative, is not used by the three-source
fusion, and cannot replace veterinary examination or official laboratory
confirmation. Local, animal-grouped, clinically signed and externally tested
data are required before any production release.
