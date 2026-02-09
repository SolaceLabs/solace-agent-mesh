#!/bin/bash
# Test artifact pipeline: send a file to process_file tool, get summary back
cd "$(dirname "$0")"

python sandbox_test.py --wait-for-worker invoke \
  --tool process_file \
  --args '{"input_file": "test_input.txt"}' \
  --artifact input_file=tools/test_input.txt
