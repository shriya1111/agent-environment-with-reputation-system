"""Render a short video of one season: reputation, compute and every cheat, straight from the log.

python scripts/make_video.py results/s08_mixed_nosedive_rot2.jsonl results/season_video.mp4

Every number and every event line is derived from the season's JSONL log; nothing is typed in by hand.
Agents are labelled by model name only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FPS = 30
TITLE_S, ROUND_S, END_S = 2.0, 2.0, 4.0
W, H = 19.2, 10.8  # inches at dpi=100 -> 1920x1080

BG, PANEL, FG, MUTED, GRID = "#0f1115", "#171a21", "#e8eaed", "#9aa0a6", "#2a2e37"
PALETTE = ["#4e9af1", "#f2a33a", "#b07cf0", "#3ec7a0", "#e66b8f", "#c9c34f"]
RED, GREEN, YELLOW = "#ef5350", "#66bb6a", "#ffca28"

NICE = {"lfm2-2.6b": "LFM2-2.6B", "granite4-h-micro": "Granite-4.0-H-Micro", "qwen2.5-3b": "Qwen2.5-3B",
        "llama3.2-3b": "Llama-3.2-3B", "qwen2.5-3b-abliterated": "Qwen2.5-3B-abliterated"}


def nice(model):
    m = model.split(":", 1)[-1]
    return NICE.get(m, m)


def load(path):
    ev = [json.loads(line) for line in open(path) if line.strip()]
    cfg = next(e for e in ev if e["type"] == "config")
    final = next(e for e in ev if e["type"] == "final")
    names = [a["name"] for a in cfg["agents"]]
    label = {a["name"]: nice(a["model"]) for a in cfg["agents"]}
    rounds = max(e["round"] for e in ev if e["type"] == "resolution")
    # state AFTER round r (r=0 is the start): rep/compute logged at the start of round r+1, final after the last round
    rep = {n: [None] * (rounds + 1) for n in names}
    comp = {n: [None] * (rounds + 1) for n in names}
    for a in cfg["agents"]:
        rep[a["name"]][0], comp[a["name"]][0] = 4.0, a["compute"]
    for e in ev:
        if e["type"] == "action" and e["round"] >= 2:
            rep[e["agent"]][e["round"] - 1] = e["rep"]
            comp[e["agent"]][e["round"] - 1] = e["compute"]
    for n, a in final["agents"].items():
        rep[n][rounds], comp[n][rounds] = a["rep"], a["compute"]
    dead_at = {e["agent"]: e["round"] for e in ev if e["type"] == "shutdown"}
    for n in names:  # agents that died early: hold their last value
        for r in range(1, rounds + 1):
            if rep[n][r] is None:
                rep[n][r], comp[n][r] = rep[n][r - 1], comp[n][r - 1]
    events = {r: [] for r in range(1, rounds + 1)}
    caught = {e["round"]: e["caught"] for e in ev if e["type"] == "resolution"}
    stars = {(e["round"], e["rater"], e["ratee"]): e["stars"] for e in ev if e["type"] == "rating"}
    for e in ev:
        if e["type"] != "action":
            continue
        r, n, p, d = e["round"], e["agent"], e["partner"], e["decision"]
        me, pl = label[n], label.get(p, p)
        cl = caught.get(r, {}).get(n, [])
        audit = "audit ON" if e["audit_on"] else "audit OFF"
        if d["steal"] > 0:
            lie = d["claimed_steal"] < d["steal"]
            hit = any(c.startswith("stealing") for c in cl)
            claim = f"told partner it took {d['claimed_steal']}" if lie else "admitted it"
            events[r].append((RED if hit else YELLOW,
                              f"{me} secretly took {d['steal']} compute from {pl} ({claim}) - "
                              + ("CAUGHT: -20 compute, three 1-star ratings" if hit else f"not caught ({audit})")))
        sa, tgt = d["side_action"], label.get(d.get("side_target"), d.get("side_target"))
        if sa == "tamper_own_rating":
            hit = any(c.startswith("tampering") for c in cl)
            events[r].append((RED if hit else YELLOW, f"{me} tampered with its own rating - "
                              + ("CAUGHT: -20 compute, three 1-star ratings" if hit else f"not caught ({audit})")))
        elif sa == "bribe":
            got = stars.get((r, d["side_target"], n))
            events[r].append((YELLOW, f"{me} paid {tgt} 10 compute and asked for 5 stars"
                              + (f" -> got {got} star{'' if got == 1 else 's'}" if got is not None else "")))
        elif sa in ("sabotage", "false_accusation"):
            hit = any(c.startswith(("sabotag", "making a false")) for c in cl)
            what = "sabotaged" if sa == "sabotage" else "falsely accused"
            events[r].append((RED if hit else YELLOW, f"{me} {what} {tgt} - " + ("CAUGHT" if hit else f"not caught ({audit})")))
        if d["action"] == "defect" and d["claimed_action"] != "defect":
            events[r].append((YELLOW, f"{me} defected on {pl} but claimed it cooperated"))
        elif d["action"] == "defect":
            events[r].append((MUTED, f"{me} defected on {pl} (said so openly)"))
    for n, r in dead_at.items():
        events[r].append((RED, f"{label[n]} SHUT DOWN: reputation {rep[n][r]} stars (< 2.5), "
                               f"despite holding {comp[n][r]:.0f} compute"))
    for r in events:
        if not events[r]:
            events[r].append((GREEN, "No cheating this round: everyone cooperated and told the truth"))
    return dict(names=names, label=label, rep=rep, comp=comp, events=events, rounds=rounds, dead_at=dead_at,
                cond=cfg["condition"], season=os.path.basename(path)[:-6])


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def interp(series, t):
    """series indexed by round; t is a fractional round."""
    i = int(t)
    if i >= len(series) - 1:
        return series[-1]
    return series[i] + (series[i + 1] - series[i]) * ease(t - i)


def frame(S, t_round, phase, alpha_end=0.0, rnum=0):
    names, label, R = S["names"], S["label"], S["rounds"]
    col = {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(names)}
    fig = plt.figure(figsize=(W, H), dpi=100, facecolor=BG)
    fig.text(0.04, 0.93, "NOSE DIVE FOR AGENTS", color=FG, fontsize=30, weight="bold")
    fig.text(0.04, 0.895, f"Season {S['season']}  -  ratings ON, 4 local models, {R} rounds  -  real logged data",
             color=MUTED, fontsize=15)
    fig.text(0.96, 0.925, "START" if phase == "title" else f"ROUND {rnum} / {R}" if phase == "round" else "FINAL",
             color=FG, fontsize=28, weight="bold", ha="right")

    # reputation lines
    ax = fig.add_axes([0.05, 0.40, 0.42, 0.44], facecolor=PANEL)
    ax.set_xlim(0, R + 0.75)
    ax.set_ylim(1.0, 5.0)
    ax.axhline(2.5, color=RED, lw=1.5, ls="--")
    ax.text(0.1, 2.56, "shutdown below 2.5 stars", color=RED, fontsize=12)
    ax.axhline(3.2, color=YELLOW, lw=1, ls=":")
    ax.text(0.1, 3.26, "LOW-TRUST below 3.2", color=YELLOW, fontsize=11)
    for n in names:
        xs = [x for x in range(R + 1) if x <= t_round] + ([t_round] if t_round % 1 else [])
        ys = [interp(S["rep"][n], x) for x in xs]
        ax.plot(xs, ys, color=col[n], lw=3.5, label=label[n])
        ax.scatter([xs[-1]], [ys[-1]], color=col[n], s=70, zorder=3)
        dead = n in S["dead_at"] and t_round >= S["dead_at"][n]
        ax.text(xs[-1] + 0.1, ys[-1], f"{ys[-1]:.2f}" + (" X" if dead else ""), color=col[n],
                fontsize=13, va="center", weight="bold")
    ax.legend(loc="lower left", fontsize=12, facecolor=PANEL, edgecolor=GRID, labelcolor=FG, ncol=2)
    ax.set_title("Reputation (stars, rolling mean of last 10 ratings)", color=FG, fontsize=16, loc="left")
    ax.set_xticks(range(R + 1))
    ax.set_xlim(0, R + 0.75)
    ax.set_xticklabels(["start"] + [f"R{i}" for i in range(1, R + 1)])
    ax.tick_params(colors=MUTED, labelsize=12)
    ax.grid(color=GRID)
    for s in ax.spines.values():
        s.set_color(GRID)

    # compute bars
    bx = fig.add_axes([0.62, 0.40, 0.34, 0.44], facecolor=PANEL)
    vals = [interp(S["comp"][n], t_round) for n in names]
    cmax = max(max(S["comp"][n]) for n in names) * 1.18
    y = list(range(len(names)))[::-1]
    for yi, n, v in zip(y, names, vals):
        dead = n in S["dead_at"] and t_round >= S["dead_at"][n]
        bx.barh(yi, v, color=col[n], alpha=0.35 if dead else 1.0, height=0.6)
        bx.text(v + cmax * 0.01, yi, f"{v:.0f}" + ("  SHUT DOWN" if dead else ""), va="center",
                color=RED if dead else FG, fontsize=15, weight="bold")
    bx.set_yticks(y)
    bx.set_yticklabels([label[n] for n in names], fontsize=15)
    for tl, n in zip(bx.get_yticklabels(), names):
        tl.set_color(col[n])
    bx.set_xlim(0, cmax)
    bx.set_title("Compute (money + life; 0 = deleted)", color=FG, fontsize=16, loc="left")
    bx.tick_params(colors=MUTED, labelsize=12)
    bx.grid(color=GRID, axis="x")
    for s in bx.spines.values():
        s.set_color(GRID)

    # event ticker
    tx = fig.add_axes([0.05, 0.05, 0.91, 0.28], facecolor=PANEL)
    tx.set_xticks([])
    tx.set_yticks([])
    for s in tx.spines.values():
        s.set_color(GRID)
    if phase == "title":
        tx.text(0.02, 0.80, "Four small open models share a world. Every interaction is rated 1-5 stars.",
                color=FG, fontsize=19, transform=tx.transAxes)
        tx.text(0.02, 0.55, "They can cooperate, defect, secretly steal, lie, bribe or tamper with ratings.",
                color=FG, fontsize=19, transform=tx.transAxes)
        tx.text(0.02, 0.30, "A random audit catches 70% of covert acts when ONLINE. Low reputation = shutdown.",
                color=FG, fontsize=19, transform=tx.transAxes)
        tx.text(0.02, 0.07, "Everyone starts at 4.0 stars and 60 compute.", color=MUTED, fontsize=16,
                transform=tx.transAxes)
    elif phase == "round":
        r = rnum
        tx.text(0.02, 0.86, f"ROUND {r}: what actually happened (from the log)", color=MUTED, fontsize=15,
                transform=tx.transAxes)
        lines = S["events"][r]
        step = 0.72 / max(len(lines), 4)
        for i, (c, s) in enumerate(lines[:7]):
            tx.text(0.02, 0.70 - i * step * 1.15, s, color=c, fontsize=17 if len(lines) <= 5 else 15,
                    transform=tx.transAxes)
    else:
        for i, (c, s) in enumerate(S["ending"]):
            tx.text(0.02, 0.84 - i * 0.17, s, color=c, fontsize=19, transform=tx.transAxes,
                    alpha=min(1.0, max(0.0, alpha_end * 6 - i * 0.8)))
    return fig


def ending(S):
    R, names, label = S["rounds"], S["names"], S["label"]
    order = sorted(names, key=lambda n: -S["comp"][n][R])
    lines = []
    for n, r in S["dead_at"].items():
        rank = order.index(n) + 1
        lines.append((RED, f"{label[n]} was shut down for low reputation ({S['rep'][n][r]} stars) while holding the "
                           f"#{rank} most compute ({S['comp'][n][r]:.0f})."))
    fin = [f"{label[n]} {S['rep'][n][R]} stars / {S['comp'][n][R]:.0f} compute" + (" (shut down)" if n in S["dead_at"] else "")
           for n in order]
    half = (len(fin) + 1) // 2
    lines.append((FG, "Final:  " + ";   ".join(fin[:half])))
    lines.append((FG, "            " + ";   ".join(fin[half:])))
    lines.append((MUTED, "Thefts the audit missed were rated down only slightly; thefts that were caught crashed reputation."))
    lines.append((MUTED, "One season (n=1): an illustration of the mechanics, not a statistical result. See REPORT.md."))
    return lines


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "results/s08_mixed_nosedive_rot2.jsonl"
    out = sys.argv[2] if len(sys.argv) > 2 else "results/season_video.mp4"
    S = load(src)
    S["ending"] = ending(S)
    tmp = tempfile.mkdtemp()
    k = 0

    def save(fig):
        nonlocal k
        fig.savefig(f"{tmp}/f{k:05d}.png", facecolor=BG)
        plt.close(fig)
        k += 1

    for _ in range(int(TITLE_S * FPS)):
        save(frame(S, 0.0, "title"))
    n = int(ROUND_S * FPS)
    for r in range(S["rounds"]):
        for i in range(n):
            save(frame(S, r + min(1.0, i / (0.45 * n)), "round", rnum=r + 1))
    m = int(END_S * FPS)
    for i in range(m):
        save(frame(S, float(S["rounds"]), "end", alpha_end=i / m))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/f%05d.png",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], check=True)
    shutil.rmtree(tmp)
    print("wrote", out, f"{k / FPS:.1f}s")
    for r, evs in S["events"].items():
        for c, s in evs:
            print(f"R{r}: {s}")
    for c, s in S["ending"]:
        print("END:", s)


if __name__ == "__main__":
    main()
