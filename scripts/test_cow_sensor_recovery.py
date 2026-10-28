"""Compile the real cow firmware recovery/sampling functions on the host.

Only hardware/serial boundaries are replaced. Function bodies and feature
statistics are read from main.cpp so tests cannot pass against a copied fix.
"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "硬件代码" / "牛身节点"


def function(source, name, required=True):
    match = re.search(
        rf"^\w[^\n;{{}}]*\b{re.escape(name)}\([^;{{}}]*\)\s*\{{.*?^\}}",
        source,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        if required:
            raise RuntimeError(f"Production function not found: {name}")
        return ""
    return match.group(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PROJECT / "src" / "main.cpp")
    args = parser.parse_args()
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ is required for the host firmware test")
    source = args.source.read_text(encoding="utf-8-sig")
    types = source[source.index("enum BehaviorClass") : source.index("struct AudioReading")]
    reading = re.search(r"^struct Reading \{.*?^\};", source, re.MULTILINE | re.DOTALL).group(0)
    diagnostics = re.search(
        r"^struct Adxl345SpiDiagnostics \{.*?^\};", source, re.MULTILINE | re.DOTALL
    )
    names = [
        "accelerationMagnitude", "motionDelta", "resetLamenessFeatureWindow",
        "finalizeLamenessWindow", "resetMotionAccumulator", "resetMotionContinuity",
        "readAdxl345SpiRegisters", "writeAdxl345SpiRegister", "adxl345Diagnostics",
        "readAdxl345SpiConfiguration", "printAdxl345SpiDiagnostics",
        "setupAdxl345Spi", "readAdxl345Spi", "sampleMotionSensors",
        "setupAddedSensors", "setupAddedI2cSensors", "recoverI2cDevices",
        "recoverSpiMotionDevices",
    ]
    optional = {
        "resetMotionContinuity", "adxl345Diagnostics", "readAdxl345SpiConfiguration",
        "printAdxl345SpiDiagnostics", "setupAddedSensors", "setupAddedI2cSensors",
        "recoverSpiMotionDevices",
    }
    blocks = [function(source, name, name not in optional) for name in names]
    prototypes = [block[: block.index("{")].strip() + ";" for block in blocks if block]
    generated = "\n".join([
        f"#define HAS_SPI_RECOVERY {int(bool(blocks[-1]))}",
        f"#define HAS_SPI_DIAGNOSTICS {int(diagnostics is not None)}",
        types, reading,
        "\n".join(prototypes),
    ])
    with tempfile.TemporaryDirectory(prefix="cow_sensor_host_") as directory:
        build = Path(directory)
        (build / "Arduino.h").write_text("#pragma once\n", encoding="ascii")
        (build / "cow_sensor_types.h").write_text(generated, encoding="utf-8")
        (build / "cow_sensor_functions.h").write_text("\n\n".join(blocks), encoding="utf-8")
        binary = build / "test_cow_sensor_recovery.exe"
        command = [
            compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-I", str(build), "-I", str(PROJECT / "include"),
            str(ROOT / "scripts" / "test_cow_sensor_recovery.cpp"), "-o", str(binary),
        ]
        print("Compiling real firmware functions with g++ (C++11)", flush=True)
        subprocess.run(command, check=True)
        result = subprocess.run([str(binary)], check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
