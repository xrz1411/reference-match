#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
python_bin="$project_dir/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  echo "未找到 .venv。请先按 README 创建虚拟环境并安装 requirements.txt。" >&2
  exit 1
fi

exec "$python_bin" "$project_dir/webui/server.py" "$@"
