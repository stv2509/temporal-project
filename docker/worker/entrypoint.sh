#!/usr/bin/env bash
set -euo pipefail

cd /app
python worker/worker.py
