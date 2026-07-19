#!/bin/bash
cd "$(dirname "$0")"
# wait for curated eval to finish (shares the chat rate limit)
while ! grep -q "=== SUMMARY ===" chat_eval_run.log 2>/dev/null; do sleep 60; done
sleep 120  # let the rate window reset
python3 -u eval_chat.py --suite chat_eval_suite_generated.json --out chat_eval_generated_results.json --pace 16 > chat_eval_generated_run.log 2>&1
echo "GENERATED EVAL COMPLETE" >> chat_eval_generated_run.log
