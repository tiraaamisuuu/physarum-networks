#!/bin/zsh
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  if command -v python3.14 >/dev/null 2>&1; then
    viewer_python=python3.14
  else
    viewer_python=python3
  fi
  "$viewer_python" -c 'import sys; sys.exit(not ((3,12) <= sys.version_info[:2] < (3,15)))' || {
    print 'The pinned viewer dependencies require Python 3.12–3.14. Install python@3.14 with Homebrew.'
    exit 1
  }
  "$viewer_python" -m venv .venv || exit 1
fi
.venv/bin/python -c 'import sys; sys.exit(not ((3,12) <= sys.version_info[:2] < (3,15)))' || {
  print 'This .venv uses an unsupported Python. Create a separate Python 3.14 environment for the viewer.'
  exit 1
}
.venv/bin/python -m pip install --disable-pip-version-check -r desktop/requirements.txt -r analysis/requirements.txt || exit 1
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel 2
if (( $? == 0 )); then
  .venv/bin/python desktop/viewer.py
else
  read 'reply?Build failed. Check the output above, then press Return.'
fi
