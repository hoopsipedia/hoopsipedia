#!/bin/bash
cd "$(dirname "$0")"
python3 -u eval_chat.py --suite chat_eval_suite_generated.json --out chat_eval_generated_results.json --pace 16 > chat_eval_generated_run2.log 2>&1
sleep 120
python3 -u eval_chat.py --suite chat_eval_suite_fuzz.json --out chat_eval_fuzz_results.json --pace 16 > chat_eval_fuzz_run2.log 2>&1
echo "ALL EVALS COMPLETE" >> chat_eval_fuzz_run2.log
