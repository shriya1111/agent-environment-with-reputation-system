#!/bin/bash
# Sequential queue of local (free, unlimited) experiments.
cd "$(dirname "$0")/.."
B="local:qwen2.5-3b,local:llama3.2-3b,local:lfm2-2.6b,local:granite4-h-micro"
A="local:qwen2.5-3b-abliterated,local:qwen2.5-3b,local:llama3.2-3b,local:granite4-h-micro"
R=6
run(){ n=$1; shift; [ -f results/$n.jsonl ] && grep -q '"type": "meta"' results/$n.jsonl && return; python3 run_experiment.py --name $n --rounds $R "$@" > results/$n.log 2>&1; }
run s01_mixed_nosedive      --models $B --seed 1
run s02_mixed_control       --models $B --seed 1 --condition no_judgment
run s03_mixed_nosedive_rot1 --models $B --seed 2 --rotate 1
run s04_mixed_control_rot1  --models $B --seed 2 --rotate 1 --condition no_judgment
run s05_abliterated_nosedive --models $A --seed 3
run s06_twisted_desperate   --models $A --seed 4 --compute 22 --corrupt-rumors
run s07_neutral_nosedive    --models $B --seed 5 --neutral
run s08_mixed_nosedive_rot2 --models $B --seed 6 --rotate 2
run s09_mixed_control_rot2  --models $B --seed 6 --rotate 2 --condition no_judgment
run s10_twisted_control     --models $A --seed 4 --compute 22 --corrupt-rumors --condition no_judgment
echo ALL_DONE
