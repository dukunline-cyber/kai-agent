#!/bin/bash
cd ~/ai-agent
set -a
source credentials/github.env
set +a
exec python3 scripts/gh_key_scanner.py
