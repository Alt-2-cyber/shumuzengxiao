#!/usr/bin/env python3
"""Audit public UCD foot-lesion data; train only with traceable clinical labels.

The public data are one sparse hind-limb Z-axis series per cow, not 20 Hz
three-position IMU recordings. This script never exports firmware or changes
clinical approval gates. Without labels it writes evidence and exits with 2.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import pickle
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "疾病识别生产落地/外部临床数据/UCD_Riaz_2025"
OUTPUT = ROOT / "疾病识别生产落地/研究模型/ucd-lameness-20261025"
REPOSITORY = "https://github.com/june18usman/UCD"
XLINK = "{http://www.w3.org/1999/xlink}href"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def inspect_csv(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    widths = sorted({len(row) for row in rows})
    implicit_index = bool(rows) and widths == [len(header) + 1]
    index_is_sequence = implicit_index and all(
        row[0] == str(i) for i, row in enumerate(rows, 1))
    return {"path": str(path), "sha256": sha256(path),
            "bytes": path.stat().st_size, "rows": len(rows),
            "header_columns": len(header), "data_row_widths": widths,
            "header_first": header[:6], "header_last": header[-6:],
            "r_implicit_row_names": index_is_sequence,
            "clinical_label_columns": [h for h in header
                                       if h.lower() in {"high", "label", "lameness"}],
            "farm_column_present": "farmer" in header,
            "cow_id_column_present": any(h.lower() in {"cow", "cow_id", "animalid"}
                                         for h in header)}


def audit_local(data: Path, output: Path) -> tuple[dict, np.ndarray, np.ndarray]:
    source = data / "source/AllCowsDataX.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    if header[0] != "farmer" or len(header) != 20001:
        raise ValueError("Unexpected UCD feature schema; no automatic column guessing")
    if len(rows) != 383 or any(len(row) != len(header) for row in rows):
        raise ValueError("Expected 383 cows and 20,000 measurements per cow")
    farms = np.array([row[0] for row in rows])
    x = np.asarray([row[1:] for row in rows], dtype=np.float64)
    if not np.isfinite(x).all():
        raise ValueError("Non-finite UCD accelerometer measurement")
    zip_results = []
    for path in sorted(data.rglob("*.zip")):
        record = {"path": str(path), "bytes": path.stat().st_size,
                  "sha256": sha256(path)}
        try:
            with zipfile.ZipFile(path) as archive:
                record["members"] = [{"name": i.filename, "bytes": i.file_size,
                                      "compressed_bytes": i.compress_size}
                                     for i in archive.infolist()]
                record["first_crc_failure"] = archive.testzip()
                record["valid"] = record["first_crc_failure"] is None
                if "AllCowsDataX.csv" in archive.namelist():
                    digest = hashlib.sha256(archive.read("AllCowsDataX.csv")).hexdigest()
                    record["csv_sha256"] = digest
                    record["csv_matches_source"] = digest == sha256(source)
        except zipfile.BadZipFile as error:
            record.update(valid=False, error=str(error))
        zip_results.append(record)
    qc = []
    for i, (values, farm) in enumerate(zip(x, farms), 1):
        qc.append({"source_row_1based": i, "farmer": str(farm),
                   "series_sha256_float64_le": hashlib.sha256(
                       values.astype("<f8").tobytes()).hexdigest(),
                   "n_measurements": values.size, "mean": float(values.mean()),
                   "std": float(values.std()), "min": float(values.min()),
                   "max": float(values.max()),
                   "mean_abs_successive_difference": float(np.abs(np.diff(values)).mean()),
                   "n_sensor_range_endpoints": int(np.isin(values, [-8.0, 7.984375]).sum())})
    write_csv(output / "cow_series_qc.csv", list(qc[0]), qc)
    partitions = []
    unique_farms = sorted(set(farms.tolist()))
    for fold, held_out in enumerate(unique_farms, 1):
        for index, farm in enumerate(farms, 1):
            partitions.append({"fold": fold, "held_out_farmer": held_out,
                               "role": "test" if farm == held_out else "train",
                               "source_row_1based": index, "farmer": str(farm)})
    write_csv(output / "unlabeled_leave_one_farm_out_partitions.csv",
              list(partitions[0]), partitions)
    r_scripts = []
    for path in sorted((data / "UCD-main").glob("*.R")):
        text = path.read_text(encoding="utf-8-sig")
        r_scripts.append({"name": path.name, "sha256": sha256(path),
                          "input_files": sorted(set(re.findall(
                              r'read\.(?:csv|table)\("([^\"]+)"', text))),
                          "requires_High": "CombConorAll$High" in text,
                          "requires_farmer": "$farmer" in text,
                          "provided_pca_not_fit_in_fold": "AfterPCA_AllCowsX" in text
                          or "AfterFPCA_AllCowsX" in text})
    protected = [ROOT / "牛行为识别数据集/esp32_motion_model/train_export_model.py",
                 ROOT / "硬件代码/现有硬件演示节点/tools/train_lameness_model.py",
                 ROOT / "硬件代码/现有硬件演示节点/tools/verify_lameness_manifest.py",
                 ROOT / "硬件代码/现有硬件演示节点/include/cattle_lameness_model.h",
                 ROOT / "硬件代码/牛身节点/include/cattle_lameness_model.h"]
    interface = {}
    tree = ast.parse(protected[1].read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                        "FEATURE_NAMES", "POSITIONS", "SAMPLE_RATE_HZ"}:
                    interface[target.id] = ast.literal_eval(node.value)
    report = {"source": inspect_csv(source),
              "dimension_reduced_files": [inspect_csv(path) for path in sorted(
                  (data / "UCD-main").glob("After*AllCowsX.csv"))],
              "archives": zip_results, "r_scripts": r_scripts,
              "farm_counts": dict(Counter(farms.tolist())),
              "shape_numeric": list(x.shape), "finite": True,
              "duplicate_numeric_series": int(len(x) - len(np.unique(x, axis=0))),
              "range": [float(x.min()), float(x.max())],
              "overall_mean": float(x.mean()), "overall_std": float(x.std()),
              "all_values_on_1_over_64_grid": bool(np.all(x * 64 == np.round(x * 64))),
              "feature_column_mean_range": [float(x.mean(0).min()), float(x.mean(0).max())],
              "feature_column_std_range": [float(x.std(0).min()), float(x.std(0).max())],
              "clinical_files_found": [str(path) for path in data.rglob("*")
                                       if path.is_file() and "combconor" in path.name.lower()],
              "existing_lameness_interface": interface,
              "protected_source_sha256": {str(path): sha256(path) for path in protected},
              "cow_identity": "One row per cow per paper; no original cow ID in feature CSV",
              "qc_row_identifier": "File row index only; not an invented clinical cow ID"}
    return report, x, farms


def inspect_paper(output: Path) -> dict:
    path = ROOT / ("疾病识别生产落地/论文资料/"
                   "01_跛行_加速度计足病机器学习验证_Riaz_2025.fulltext.xml")
    root = ET.parse(path).getroot()
    selected = []
    terms = ("sampling procedure", "1500", "data availability", "20,000",
             "github", "severe foot lesions", "diagnosed by", "ax3")
    for element in root.findall(".//p"):
        text = "".join(element.itertext())
        if any(term in text.lower() for term in terms):
            selected.append(text)
    supplements = [{"id": e.get("id"), "href": e.get(XLINK),
                    "description": " ".join("".join(e.itertext()).split())}
                   for e in root.findall(".//supplementary-material")]
    result = {"path": str(path), "sha256": sha256(path),
              "doi": "10.1371/journal.pone.0325927", "paragraphs": selected,
              "supplements": supplements,
              "repository_links": [e.get(XLINK) for e in root.findall(".//ext-link")
                                   if "github" in (e.get(XLINK) or "")]}
    save_json(output / "paper_evidence.json", result)
    return result


class PublicEvidence:
    def __init__(self, output: Path):
        self.output = output
        log = output / "retrieval_log.json"
        self.records: list[dict] = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []

    def fetch(self, name: str, url: str, limit: int = 12_000_000) -> bytes | None:
        for previous in reversed(self.records):
            if previous.get("name") == name and previous.get("url") == url and previous.get("status") == 200:
                cached = Path(previous["path"])
                if cached.is_file() and sha256(cached) == previous.get("sha256"):
                    print("CACHE", name, flush=True)
                    return cached.read_bytes()
        record = {"name": name, "url": url,
                  "retrieved_at_utc": datetime.now(UTC).isoformat()}
        print("GET", name, flush=True)
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 UCD-public-data-evidence/1.0"})
            with urllib.request.urlopen(request, timeout=18) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise ValueError(f"Response exceeds download cap {limit}")
                record.update(status=response.status, final_url=response.url,
                              content_type=response.headers.get("Content-Type"))
        except urllib.error.HTTPError as error:
            body = error.read(min(limit, 250000))
            record.update(status=error.code, error=str(error))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            body = None
            record.update(status=None, error=f"{type(error).__name__}: {error}")
        if body is None:
            # A bounded fallback uses the same Windows proxy route and TLS checks.
            target = self.output / "public_sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            environment = os.environ.copy()
            for scheme, proxy in urllib.request.getproxies().items():
                if scheme in {"http", "https"}:
                    environment.setdefault(scheme.upper() + "_PROXY", proxy)
            command = ["curl.exe", "--ssl-revoke-best-effort", "--silent", "--show-error",
                       "--location", "--connect-timeout", "7", "--max-time", "20",
                       "--max-filesize", str(limit), "--output", str(target),
                       "--write-out", "%{http_code}", url]
            try:
                fallback = subprocess.run(command, capture_output=True, text=True,
                                          encoding="utf-8", errors="replace", env=environment,
                                          timeout=25)
                record["curl_fallback"] = {"returncode": fallback.returncode,
                                            "http_code": fallback.stdout.strip(),
                                            "error": fallback.stderr.strip()}
                if fallback.returncode == 0 and fallback.stdout.strip().isdigit():
                    body = target.read_bytes()
                    record["initial_error"] = record.pop("error", None)
                    record["status"] = int(fallback.stdout.strip())
            except (OSError, subprocess.SubprocessError) as error:
                record["curl_fallback_error"] = str(error)
        if body is not None:
            target = self.output / "public_sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            record.update(path=str(target), bytes=len(body), sha256=sha256(target))
        self.records.append(record)
        save_json(self.output / "retrieval_log.json", self.records)
        print("HTTP", record.get("status"), record.get("bytes", 0), flush=True)
        return body if record.get("status") == 200 else None


def git_history(output: Path) -> dict:
    destination = output / "public_sources/UCD.git"
    log = output / "git_commands.json"
    commands = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    environment = os.environ.copy()
    # urllib uses Windows Internet Settings; Git needs explicit proxy variables.
    for scheme, proxy in urllib.request.getproxies().items():
        if scheme in {"http", "https"}:
            environment.setdefault(scheme.upper() + "_PROXY", proxy)
    environment["GIT_TERMINAL_PROMPT"] = "0"

    def run(arguments: list[str], timeout: int = 45) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(arguments, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=timeout,
                                    env=environment)
            commands.append({"args": arguments, "returncode": result.returncode,
                             "stdout": result.stdout, "stderr": result.stderr})
            save_json(output / "git_commands.json", commands)
            return result
        except subprocess.TimeoutExpired as error:
            commands.append({"args": arguments, "error": str(error)})
            save_json(output / "git_commands.json", commands)
            raise

    try:
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            result = run(["git", "clone", "--mirror", REPOSITORY + ".git", str(destination)])
            if result.returncode:
                return {"complete": False, "reason": "clone failed"}
        prefix = ["git", "--git-dir", str(destination)]
        head_probe = run(prefix + ["rev-parse", "--verify", "HEAD"])
        if head_probe.returncode:
            fetched = run(prefix + ["fetch", "origin", "+refs/*:refs/*"])
            if fetched.returncode:
                return {"complete": False, "reason": "fetch failed"}
        commits = run(prefix + ["log", "--all", "--format=%H %aI %s"])
        objects = run(prefix + ["rev-list", "--objects", "--all"])
        names = run(prefix + ["log", "--all", "--name-status", "--format=commit %H"])
        head = run(prefix + ["rev-parse", "HEAD"])
        refs = run(prefix + ["show-ref"])
        if any(r.returncode for r in (commits, objects, names, head, refs)):
            return {"complete": False, "reason": "git history inspection failed"}
        archive_members = []
        for line in objects.stdout.splitlines():
            fields = line.split(" ", 1)
            if len(fields) == 2 and fields[1].lower().endswith(".zip"):
                blob = subprocess.run(prefix + ["cat-file", "blob", fields[0]],
                                      capture_output=True, timeout=15, check=True).stdout
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    archive_members.append({"object": fields[0], "path": fields[1],
                                            "sha256": hashlib.sha256(blob).hexdigest(),
                                            "members": archive.namelist(),
                                            "crc_failure": archive.testzip()})
        paths = [line.split(" ", 1)[1] for line in objects.stdout.splitlines()
                 if " " in line and line.split(" ", 1)[1]]
        return {"complete": True, "repository": REPOSITORY,
                "head_commit": head.stdout.strip(), "refs": refs.stdout.splitlines(),
                "commits": commits.stdout.splitlines(), "historical_paths": sorted(set(paths)),
                "clinical_filename_matches": [p for p in paths if "combconor" in p.lower()],
                "license_filename_matches": [p for p in paths
                                             if "license" in p.lower() or "licence" in p.lower()],
                "archive_members": archive_members}
    except (subprocess.SubprocessError, OSError, zipfile.BadZipFile) as error:
        return {"complete": False, "error": f"{type(error).__name__}: {error}"}


def collect_online(output: Path) -> dict:
    evidence = PublicEvidence(output)
    evidence.fetch("github_repository.html", REPOSITORY)
    evidence.fetch("github_commits.atom", REPOSITORY + "/commits/main.atom")
    evidence.fetch("github_branches.json", "https://api.github.com/repos/june18usman/UCD/branches")
    evidence.fetch("github_forks.json", "https://api.github.com/repos/june18usman/UCD/forks?per_page=100")
    evidence.fetch("github_labels.csv.response", "https://raw.githubusercontent.com/"
                   "june18usman/UCD/main/CombConorAll.csv")
    evidence.fetch("github_labels.xlsx.response", "https://raw.githubusercontent.com/"
                   "june18usman/UCD/main/CombConorAll.xlsx")
    evidence.fetch("plos_article.html", "https://journals.plos.org/plosone/"
                   "article?id=10.1371/journal.pone.0325927")
    evidence.fetch("plos_S1_Table.docx", "https://journals.plos.org/plosone/"
                   "article/file?type=supplementary&id=10.1371/journal.pone.0325927.s001")
    supplement = output / "public_sources/plos_S1_Table.docx"
    if supplement.is_file() and zipfile.is_zipfile(supplement):
        with zipfile.ZipFile(supplement) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            table = root.findall(".//w:tbl", namespace)
            table_rows = []
            for row in table[0].findall("w:tr", namespace):
                table_rows.append(["".join(t.text or "" for t in cell.findall(".//w:t", namespace))
                                   for cell in row.findall("w:tc", namespace)])
            fields = ["reduction", "validation", "model", "metric", "paper_estimate_95ci_percent"]
            if any(len(row) != 5 for row in table_rows):
                raise ValueError("Unexpected S1 table structure")
            write_csv(output / "paper_reported_metrics.csv", fields,
                      [dict(zip(fields, row)) for row in table_rows[1:]])
            save_json(output / "supplement_audit.json", {
                "sha256": sha256(supplement), "zip_crc_failure": archive.testzip(),
                "tables": len(table), "aggregate_metric_rows": len(table_rows) - 1,
                "headers": table_rows[0], "individual_cow_labels_present": False,
                "basis": "Single table has reduction/validation/model/metric/estimate columns only",
                "metric_origin": "Published paper, not validation performed in this run"})
    history = git_history(output)
    save_json(output / "repository_history.json", history)
    return {"retrievals": evidence.records, "history": history}


def discover_public_datasets(output: Path) -> dict:
    evidence = PublicEvidence(output)
    searches = [
        ("datacite_ucd_labels.json", "https://api.datacite.org/dois?" + urllib.parse.urlencode(
            {"query": "CombConorAll", "page[size]": 10})),
        ("datacite_lameness_accelerometer.json", "https://api.datacite.org/dois?" + urllib.parse.urlencode(
            {"query": "lameness AND accelerometer", "page[size]": 25})),
        ("datacite_cattle_accelerometer_all.json", "https://api.datacite.org/dois?" + urllib.parse.urlencode(
            {"query": "cattle AND accelerometer", "page[size]": 100})),
        ("datacite_lameness_all.json", "https://api.datacite.org/dois?" + urllib.parse.urlencode(
            {"query": "lameness", "page[size]": 100})),
        ("zenodo_clinical_cattle_sensors.json", "https://zenodo.org/api/records?" + urllib.parse.urlencode(
            {"q": '(cattle AND lameness AND accelerometer)', "type": "dataset", "size": 20})),
        ("zenodo_cattle_multiple_positions.json", "https://zenodo.org/api/records?" + urllib.parse.urlencode(
            {"q": '(cattle AND accelerometer AND (neck OR back OR leg))',
             "type": "dataset", "size": 20})),
        ("figshare_riaz_supplements.json", "https://api.figshare.com/v2/articles?"
         "resource_doi=10.1371/journal.pone.0325927"),
        ("crossref_original_logan_study.json", "https://api.crossref.org/works/10.3168/jds.2023-23928")]
    results = []
    for name, url in searches:
        body = evidence.fetch(name, url, limit=3_000_000)
        entry = {"name": name, "url": url, "retrieved": body is not None}
        if body:
            try:
                value = json.loads(body)
                if name.startswith("datacite"):
                    entry["total"] = value.get("meta", {}).get("total")
                    entry["candidates"] = [
                        {"doi": item["id"], **{key: item["attributes"].get(key)
                                                for key in ("titles", "url", "descriptions", "rightsList")}}
                        for item in value.get("data", [])]
                elif name.startswith("zenodo"):
                    entry["total"] = value.get("hits", {}).get("total")
                    entry["candidates"] = [
                        {"id": item["id"], **{key: item["metadata"].get(key)
                                                for key in ("title", "doi", "description", "license")},
                         "files": [{key: file.get(key) for key in ("key", "size", "checksum", "links")}
                                   for file in item.get("files", [])]}
                        for item in value.get("hits", {}).get("hits", [])]
                else:
                    entry["metadata"] = value
            except (ValueError, TypeError, KeyError) as error:
                entry["parse_error"] = str(error)
        results.append(entry)
        save_json(output / "alternative_dataset_search.json", results)
    return {"queries": len(results), "successful_queries": sum(e["retrieved"] for e in results)}


def index_alternative_metadata(output: Path) -> None:
    path = output / "public_sources/datacite_cattle_accelerometer_all.json"
    if not path.is_file():
        return
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in value.get("data", []):
        attributes = item["attributes"]
        rows.append({"doi": item["id"],
                     "title": attributes["titles"][0]["title"],
                     "resource_type": attributes.get("types", {}).get("resourceTypeGeneral"),
                     "url": attributes.get("url"),
                     "license": "; ".join(right.get("rights", "") for right
                                          in attributes.get("rightsList", [])),
                     "clinical_data_verified": "no; metadata only"})
    if rows:
        write_csv(output / "alternative_dataset_inventory.csv", list(rows[0]), rows)


def verify_evidence(output: Path, report: dict, status: dict) -> dict:
    checks = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    source = report["source"]
    check("complete_source_csv", source["rows"] == 383 and source["data_row_widths"] == [20001],
          {"rows": source["rows"], "columns": source["header_columns"]})
    check("source_csv_hash_unchanged", sha256(Path(source["path"])) == source["sha256"], source["sha256"])
    complete = [a for a in report["archives"] if a.get("csv_matches_source")]
    check("zip_crc_and_source_match", len(complete) == 1 and complete[0]["valid"], len(complete))
    with (output / "unlabeled_leave_one_farm_out_partitions.csv").open(
            encoding="utf-8", newline="") as handle:
        partitions = list(csv.DictReader(handle))
    tests = Counter()
    disjoint = True
    for fold in {row["fold"] for row in partitions}:
        fold_rows = [row for row in partitions if row["fold"] == fold]
        train_rows = {int(r["source_row_1based"]) for r in fold_rows if r["role"] == "train"}
        test_rows = {int(r["source_row_1based"]) for r in fold_rows if r["role"] == "test"}
        train_farms = {r["farmer"] for r in fold_rows if r["role"] == "train"}
        test_farms = {r["farmer"] for r in fold_rows if r["role"] == "test"}
        disjoint &= not train_rows & test_rows and not train_farms & test_farms
        disjoint &= len(fold_rows) == 383 and train_rows | test_rows == set(range(1, 384))
        disjoint &= len(test_farms) == 1 and len(train_farms) == 10
        tests.update(test_rows)
    check("farm_partitions_disjoint_and_exhaustive", disjoint and len(partitions) == 4213,
          {"folds": len({r["fold"] for r in partitions}), "rows": len(partitions)})
    check("each_source_cow_row_tested_once", len(tests) == 383 and set(tests.values()) == {1},
          len(tests))
    if not status["model_created"]:
        forbidden = [str(path.relative_to(output)) for path in output.rglob("*")
                     if path.is_file() and path.suffix in {".pkl", ".joblib", ".onnx", ".h", ".tflite"}]
        check("no_model_or_firmware_artifacts", not forbidden, forbidden)
        check("no_measured_metrics_without_labels", not (output / "validation_metrics.json").exists()
              and not (output / "out_of_fold_predictions.csv").exists(), status["status"])
    protected = report["protected_source_sha256"]
    check("existing_programs_and_gates_unchanged", all(sha256(Path(p)) == digest
          for p, digest in protected.items()), list(protected))
    history_path = output / "repository_history.json"
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
        check("full_official_git_history_checked", history.get("complete", False),
              {"head": history.get("head_commit"), "commits": len(history.get("commits", [])),
               "clinical_filename_matches": history.get("clinical_filename_matches")})
    result = {"at_utc": datetime.now(UTC).isoformat(), "checks": checks,
              "passed": all(record["passed"] for record in checks),
              "model_performance_verified": False if not status["model_created"] else True}
    save_json(output / "verification_results.json", result)
    if not result["passed"]:
        raise RuntimeError("Research evidence verification failed; see verification_results.json")
    return result


def load_labels(path: Path, provenance_path: Path, data_hash: str,
                farms: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    for key in ("source_url", "license", "target_definition", "row_alignment_evidence",
                "clinical_reference"):
        if not isinstance(provenance.get(key), str) or not provenance[key].strip():
            raise ValueError(f"Missing clinical label provenance: {key}")
    if not provenance["source_url"].startswith("https://"):
        raise ValueError("A public HTTPS clinical label source is required")
    if provenance.get("labels_sha256") != sha256(path):
        raise ValueError("Clinical label file SHA-256 does not match provenance")
    if provenance.get("ucd_data_sha256") != data_hash:
        raise ValueError("Label row mapping does not identify this exact UCD feature file")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(farms):
        raise ValueError("A complete verified 383-cow mapping is required")
    if any(not {"source_row_1based", "cow_id", "High", "farmer"} <= set(row)
           for row in rows):
        raise ValueError("Labels require source_row_1based,cow_id,High,farmer")
    rows.sort(key=lambda row: int(row["source_row_1based"]))
    if [int(row["source_row_1based"]) for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Label row mapping has duplicate or missing source rows")
    if any(row["farmer"] != str(farm) for row, farm in zip(rows, farms)):
        raise ValueError("Clinical label farm IDs conflict with the UCD feature table")
    if any(row["High"] not in {"0", "1"} for row in rows):
        raise ValueError("Clinical High labels must be observed binary 0/1")
    cows = np.array([row["cow_id"].strip() for row in rows])
    if any(not cow for cow in cows) or len(np.unique(cows)) != len(cows):
        raise ValueError("Unique original cow IDs are required; row IDs are not clinical IDs")
    y = np.array([int(row["High"]) for row in rows], dtype=np.int8)
    if len(np.unique(y)) != 2:
        raise ValueError("Clinical labels contain only one class")
    return y, cows, provenance


def train(x: np.ndarray, y: np.ndarray, cows: np.ndarray, farms: np.ndarray,
          output: Path, provenance: dict) -> dict:
    import scipy
    import sklearn
    from sklearn.base import clone
    from sklearn.decomposition import PCA
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (accuracy_score, average_precision_score,
                                 balanced_accuracy_score, brier_score_loss,
                                 confusion_matrix, roc_auc_score)
    from sklearn.model_selection import LeaveOneGroupOut, StratifiedGroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    def metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict:
        predicted = (probabilities >= 0.5).astype(int)
        tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
        return {"n": len(labels), "positives": int(labels.sum()),
                "accuracy": float(accuracy_score(labels, predicted)),
                "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)),
                "sensitivity": float(tp / (tp + fn)) if tp + fn else None,
                "specificity": float(tn / (tn + fp)) if tn + fp else None,
                "ppv": float(tp / (tp + fp)) if tp + fp else None,
                "auc": float(roc_auc_score(labels, probabilities))
                if len(np.unique(labels)) == 2 else None,
                "average_precision": float(average_precision_score(labels, probabilities))
                if labels.sum() else None,
                "brier_score": float(brier_score_loss(labels, probabilities)),
                "confusion_matrix_tn_fp_fn_tp": [int(tn), int(fp), int(fn), int(tp)]}

    models = {
        "prevalence_baseline": DummyClassifier(strategy="prior"),
        "raw_z_random_forest": RandomForestClassifier(
            n_estimators=150, max_features=20, min_samples_leaf=5,
            class_weight="balanced", random_state=20261025, n_jobs=2),
        "train_fold_pca_logistic": make_pipeline(
            StandardScaler(), PCA(n_components=20, svd_solver="randomized",
                                  random_state=20261025),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000,
                               random_state=20261025))}
    splits = {
        "cow_grouped_5fold": list(StratifiedGroupKFold(
            n_splits=5, shuffle=True, random_state=20261025).split(x, y, cows)),
        "leave_one_farm_out": list(LeaveOneGroupOut().split(x, y, farms))}
    results = {"threshold": 0.5, "selection": "Fixed models; no test-fold tuning",
               "target": "Severe foot lesions, case definition 3; not mobility score",
               "versions": {"python": sys.version, "numpy": np.__version__,
                            "scipy": scipy.__version__, "sklearn": sklearn.__version__},
               "provenance": provenance, "evaluations": {}}
    predictions = []
    partition_rows = []
    for scheme, folds in splits.items():
        results["evaluations"][scheme] = {}
        for fold, (train_indices, test_indices) in enumerate(folds, 1):
            assert not set(cows[train_indices]) & set(cows[test_indices])
            if scheme == "leave_one_farm_out":
                assert not set(farms[train_indices]) & set(farms[test_indices])
            if len(np.unique(y[train_indices])) != 2:
                raise ValueError("A training fold has only one clinical class")
            for role, indices in (("train", train_indices), ("test", test_indices)):
                partition_rows.extend({"scheme": scheme, "fold": fold, "role": role,
                                       "source_row_1based": int(i) + 1,
                                       "cow_id": str(cows[i]), "farmer": str(farms[i])}
                                      for i in indices)
        for name, estimator in models.items():
            probabilities = np.full(len(y), np.nan)
            fold_scores = []
            for fold, (train_indices, test_indices) in enumerate(folds, 1):
                model = clone(estimator).fit(x[train_indices], y[train_indices])
                probability = model.predict_proba(x[test_indices])[:, 1]
                probabilities[test_indices] = probability
                fold_scores.append({"fold": fold, **metrics(y[test_indices], probability)})
                predictions.extend({"scheme": scheme, "model": name, "fold": fold,
                                    "source_row_1based": int(i) + 1, "cow_id": str(cows[i]),
                                    "farmer": str(farms[i]), "High": int(y[i]),
                                    "probability": float(p)}
                                   for i, p in zip(test_indices, probability))
            if not np.isfinite(probabilities).all():
                raise ValueError("Incomplete out-of-fold predictions")
            results["evaluations"][scheme][name] = {
                "pooled_out_of_fold": metrics(y, probabilities), "folds": fold_scores}
    write_csv(output / "validation_partitions.csv", list(partition_rows[0]), partition_rows)
    write_csv(output / "out_of_fold_predictions.csv", list(predictions[0]), predictions)
    save_json(output / "validation_metrics.json", results)
    for name, estimator in models.items():
        if name != "prevalence_baseline":
            fitted = clone(estimator).fit(x, y)
            with (output / f"{name}.research-only.pkl").open("wb") as handle:
                pickle.dump(fitted, handle, protocol=5)
    return results


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--discover", action="store_true",
                        help="Bounded public clinical/multiple-position dataset metadata search")
    parser.add_argument("--verify", action="store_true",
                        help="Check actual source hashes, farm partitions and model absence")
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    if bool(args.labels) != bool(args.provenance):
        parser.error("--labels and --provenance are required together")
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.labels and list(args.output.glob("*.pkl")):
        parser.error("Existing model files found: choose a clean evidence output directory")
    report, x, farms = audit_local(args.data, args.output)
    report["paper"] = inspect_paper(args.output)
    report["run"] = {"at_utc": datetime.now(UTC).isoformat(), "python": sys.version,
                     "numpy": np.__version__, "script": str(Path(__file__).resolve()),
                     "script_sha256": sha256(Path(__file__)), "args": vars(args)}
    report["run"]["args"] = {key: str(value) if isinstance(value, Path) else value
                             for key, value in report["run"]["args"].items()}
    save_json(args.output / "local_data_audit.json", report)
    if args.online:
        collect_online(args.output)
    if args.discover:
        discover_public_datasets(args.output)
    index_alternative_metadata(args.output)
    status = {"status": "blocked_missing_clinical_labels", "model_created": False,
              "production_eligible": False, "rows": len(x), "farms": len(np.unique(farms)),
              "missing": ["Verified clinical High labels and exact cow-to-row linkage"],
              "deployment_compatibility": {
                  "compatible": False, "source": "One hind-limb Z axis; ~30 s sparse points over 7 days",
                  "target": "Neck/body/leg ADXL345 XYZ at 20 Hz; 10 s windows",
                  "reason": "Missing positions, axes, high-rate timing and target-domain clinical validation"},
              "approval_gates_changed": False}
    if args.labels:
        y, cows, provenance = load_labels(args.labels, args.provenance,
                                         report["source"]["sha256"], farms)
        train(x, y, cows, farms, args.output, provenance)
        status.update(status="research_training_complete", model_created=True, missing=[])
    save_json(args.output / "training_status.json", status)
    protected_after = {path: sha256(Path(path)) for path in report["protected_source_sha256"]}
    if protected_after != report["protected_source_sha256"]:
        raise RuntimeError("A protected source changed during the research run")
    if args.verify:
        verify_evidence(args.output, report, status)
    manifest = [{"path": str(path.relative_to(args.output)), "bytes": path.stat().st_size,
                 "sha256": sha256(path)} for path in sorted(args.output.rglob("*"))
                if path.is_file() and "UCD.git" not in path.parts
                and path.name != "artifact_manifest.json"]
    save_json(args.output / "artifact_manifest.json", manifest)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["model_created"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
