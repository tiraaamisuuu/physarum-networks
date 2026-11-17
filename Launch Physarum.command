#!/bin/zsh
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || exit 1
fi
.venv/bin/python -m pip install --disable-pip-version-check -r desktop/requirements.txt -r analysis/requirements.txt || exit 1
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel 2
if (( $? == 0 )); then
  .venv/bin/python desktop/viewer.py
else
  read 'reply?Build failed. Check the output above, then press Return.'
fi
