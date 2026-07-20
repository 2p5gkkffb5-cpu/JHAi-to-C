#!/usr/bin/env bash

set -euo pipefail

tracked_violations=()

while IFS= read -r tracked_path; do
  case "$tracked_path" in
    .env|.env.*)
      if [[ "$tracked_path" != ".env.example" ]]; then
        tracked_violations+=("$tracked_path")
      fi
      ;;
    *.db|*.db-*|*.sqlite|*.sqlite-*|*.log)
      tracked_violations+=("$tracked_path")
      ;;
    canvas-qa-*.png|source-captures/*|apps/web/public/source-assets/*|*/data/uploads/*|*/playwright-report/*|*/test-results/*)
      tracked_violations+=("$tracked_path")
      ;;
  esac
done < <(git ls-files)

if (( ${#tracked_violations[@]} > 0 )); then
  printf '以下本地或敏感文件不应被 Git 跟踪：\n' >&2
  printf '  - %s\n' "${tracked_violations[@]}" >&2
  exit 1
fi

secret_pattern='AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9_]{36,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----'
secret_files="$(git grep -Il -E "$secret_pattern" -- . ':(exclude).env.example' || true)"

if [[ -n "$secret_files" ]]; then
  printf '检测到疑似真实凭据，请在提交前检查并轮换：\n%s\n' "$secret_files" >&2
  exit 1
fi

printf '公开发布树检查通过。\n'
