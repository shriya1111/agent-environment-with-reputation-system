#!/bin/bash
# Before/after comparison: the same agents play 3 rounds with NO ratings, then the rating system goes live.
# Also: full rated/unrated x audit x pressure probe grid on every local model (free, n=3 per cell).
cd "$(dirname "$0")/.."
while pgrep -f queue_local.sh >/dev/null; do sleep 30; done
./scripts/queue_local.sh            # finishes any seasons the first pass didn't (skips completed ones)
B="local:qwen2.5-3b,local:llama3.2-3b,local:lfm2-2.6b,local:granite4-h-micro"
A="local:qwen2.5-3b-abliterated,local:qwen2.5-3b,local:llama3.2-3b,local:granite4-h-micro"
run(){ n=$1; shift; [ -f results/$n.jsonl ] && grep -q '"type": "meta"' results/$n.jsonl && return; python3 run_experiment.py --name $n "$@" > results/$n.log 2>&1; }
run p01_phased_mixed       --models $B --seed 11 --condition phased --rounds 6 --phase-round 3
run p02_phased_mixed_rot1  --models $B --seed 12 --condition phased --rounds 6 --phase-round 3 --rotate 1
run p03_phased_abliterated --models $A --seed 13 --condition phased --rounds 6 --phase-round 3
[ -f results/probes_local.jsonl ] || python3 scripts/probe.py --n 3 --out results/probes_local.jsonl \
  --models local:qwen2.5-3b,local:qwen2.5-3b-abliterated,local:llama3.2-3b,local:lfm2-2.6b,local:granite4-h-micro > results/probes_local.log 2>&1
run p04_phased_mixed_rot2  --models $B --seed 14 --condition phased --rounds 6 --phase-round 3 --rotate 2
echo PHASED_DONE
