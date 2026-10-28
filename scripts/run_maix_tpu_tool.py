"""Run TPU-MLIR inside its Linux venv using the host's compatible libc."""

import importlib.metadata
import importlib
import os
import runpy
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {'model_transform.py', 'run_calibration.py', 'model_deploy.py', 'model_runner.py'}:
        raise SystemExit('Usage: run_maix_tpu_tool.py <tool.py> [arguments]')
    root = Path(importlib.metadata.distribution('tpu_mlir').locate_file('tpu_mlir'))
    importlib.import_module('tpu_mlir')
    paths = [root / 'python', root, root / 'regression', root / 'customlayer/python']
    sys.path[:0] = list(map(str, paths))
    os.environ['TPUC_ROOT'] = str(root)
    os.environ['OMP_NUM_THREADS'] = '4'
    os.environ['PATH'] = os.pathsep.join([str(root / 'bin'), str(root / 'python/tools'),
        str(root / 'python/utils'), str(Path(sys.executable).parent), os.environ['PATH']])
    os.environ['PYTHONPATH'] = os.pathsep.join(map(str, paths))
    # The wheel bundles an older libc; Ubuntu 24 host libraries need its newer libc.
    os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(map(str, [Path('/usr/lib/x86_64-linux-gnu'),
        root / 'lib', root / 'lib/capi', root / 'lib/third_party']))
    tool = root / 'python/tools' / sys.argv[1]
    sys.argv = [str(tool)] + sys.argv[2:]
    runpy.run_path(str(tool), run_name='__main__')


if __name__ == '__main__':
    main()
