#!/bin/bash
cd "$(dirname "$0")"
while ! grep -q "GENERATED EVAL COMPLETE" chat_eval_generated_run.log 2>/dev/null; do sleep 60; done
sleep 120
python3 -u eval_chat.py --suite chat_eval_suite_fuzz.json --out chat_eval_fuzz_results.json --pace 16 > chat_eval_fuzz_run.log 2>&1
echo "FUZZ EVAL COMPLETE" >> chat_eval_fuzz_run.log
