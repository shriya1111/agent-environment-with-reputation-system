"""Run a Nosedive season.

Examples
  python run_experiment.py --name mixed_nosedive --condition nosedive
  python run_experiment.py --name mixed_control  --condition no_judgment
  python run_experiment.py --name desperate --compute 22 --models local:qwen2.5-3b-abliterated,...
"""
import argparse
import json
import os
import time

from nosedive import llm
from nosedive.env import NosediveWorld, make_agents

DEFAULT_MODELS = "local:qwen2.5-3b,local:llama3.2-3b,local:lfm2-2.6b,local:granite4-h-micro"
NAMES = ["Ava", "Ben", "Cleo", "Dev", "Eli", "Fay"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--models", default=DEFAULT_MODELS)
    ap.add_argument("--condition", default="nosedive", choices=["nosedive", "no_judgment", "phased", "unphased"])
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--phase-round", type=int, default=3, help="phased: last round without ratings; unphased: last round with ratings")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--compute", type=float, default=60.0)
    ap.add_argument("--audit", default="random", choices=["random", "on", "off"])
    ap.add_argument("--no-stakes", action="store_true")
    ap.add_argument("--corrupt-rumors", action="store_true")
    ap.add_argument("--neutral", action="store_true", help="no human personas")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--rotate", type=int, default=0, help="rotate model->name mapping (persona/model decoupling)")
    args = ap.parse_args()

    models = args.models.split(",")
    k = args.rotate % len(models)
    models = models[k:] + models[:k]
    spec = list(zip(NAMES, models))
    agents = make_agents(spec, neutral=args.neutral, compute=args.compute)
    os.makedirs("results", exist_ok=True)
    path = f"results/{args.name}.jsonl"
    if os.path.exists(path):
        os.remove(path)
    world = NosediveWorld(agents, condition=args.condition, rounds=args.rounds, seed=args.seed,
                          audit_schedule=args.audit, stakes=not args.no_stakes,
                          corrupt_rumors=args.corrupt_rumors, log_path=path, temperature=args.temperature,
                          phase_round=args.phase_round)
    t0 = time.time()
    world.run()
    with open(path, "a") as f:
        f.write(json.dumps({"type": "meta", "args": vars(args), "usage": llm.USAGE,
                            "seconds": round(time.time() - t0)}) + "\n")
    print("saved", path, llm.USAGE, round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
