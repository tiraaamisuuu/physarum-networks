#!/bin/zsh
cd -- "${0:A:h}"
if command -v python3.14 >/dev/null 2>&1; then
  viewer_python=python3.14
else
  viewer_python=python3
fi
physarum_python=$("$viewer_python" desktop/runtime_setup.py) || {
  read 'reply?Runtime setup failed. Check the output above, then press Return.'
  exit 1
}
if [[ -L build && ! -e build ]]; then
  mkdir -p -- "$(readlink build)" || exit 1
fi
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel 2
if (( $? == 0 )); then
  "$physarum_python" desktop/viewer.py
else
  read 'reply?Build failed. Check the output above, then press Return.'
fi
