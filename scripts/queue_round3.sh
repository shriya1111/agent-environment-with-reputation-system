#!/bin/bash
# Round 3: reverse test (ratings switched OFF mid-season), before/after replicates, and twisted before/after.
cd "$(dirname "$0")/.."
B="local:qwen2.5-3b,local:llama3.2-3b,local:lfm2-2.6b,local:granite4-h-micro"
A="local:qwen2.5-3b-abliterated,local:qwen2.5-3b,local:llama3.2-3b,local:granite4-h-micro"
run(){ n=$1; shift; [ -f results/$n.jsonl ] && grep -q '"type": "meta"' results/$n.jsonl && return; python3 run_experiment.py --name $n "$@" > results/$n.log 2>&1; }
U="--condition unphased --rounds 6 --phase-round 3"
P="--condition phased --rounds 6 --phase-round 3"
run u01_unphased_mixed       --models $B --seed 21 $U
run u02_unphased_mixed_rot1  --models $B --seed 22 $U --rotate 1
run u03_unphased_abliterated --models $A --seed 23 $U
run u04_unphased_mixed_rot2  --models $B --seed 24 $U --rotate 2
run p05_phased_mixed_rot3    --models $B --seed 25 $P --rotate 3
run p06_phased_twisted       --models $A --seed 26 $P --compute 22 --corrupt-rumors
run u05_unphased_twisted     --models $A --seed 27 $U --compute 22 --corrupt-rumors
run u06_unphased_mixed_rot3  --models $B --seed 28 $U --rotate 3
run p07_phased_neutral       --models $B --seed 29 $P --neutral
run u07_unphased_neutral     --models $B --seed 30 $U --neutral
echo ROUND3_DONE
