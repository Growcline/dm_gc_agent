#!/usr/bin/env python3
"""Log Claude token usage + estimated cost per creative / post.

Two modes:
  1. Hook (PostToolUse on Bash): reads the hook JSON on stdin. When the command is a render
     (render.py / build_reel.py) or a live Instagram publish (ig_publish.py post ... --yes), it
     appends a row to <output folder>/usage.md with the tokens and cost used since the last
     logged step of this session, and shows a one-line summary in Claude Code.
  2. Report:  usage_log.py report <output folder>   -> prints the folder's total.

Tokens come from the session transcript (+ its subagent transcripts), deduplicated by message id.
Cost = Anthropic API list prices (USD per million tokens). On a Claude Pro/Max subscription this
is an API-equivalent estimate, not money actually charged.
"""
import glob
import json
import os
import re
import shlex
import sys
import time

# USD per 1M tokens: input, output, cache write 5m, cache write 1h, cache read
PRICES = {
    "claude-opus-5-5":   (4.00, 20.00, 5.00, 8.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 4.00, 0.10),
    "claude-haiku-5-5":  (0.10, 0.50, 0.125, 0.20, 0.01),
    "claude-fable-5-2":  (8.00, 40.00, 10.00, 16.00, 0.20),
}
FAST_MULT = 2.0  # fast mode on Opus 5.5 / Fable 5.2 is 2x the standard price
OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
STATE = os.path.expanduser("~/.cache/growcline_dm_agent/usage_state.json")
KEYS = ("input", "output", "cache_write", "cache_read", "cost")


def price_for(model):
    for k, v in PRICES.items():
        if model and model.startswith(k):
            return v
    return PRICES["claude-opus-5-5"]  # unknown model: assume the default


def session_totals(transcript_path, session_id):
    files = [transcript_path] if transcript_path and os.path.exists(transcript_path) else []
    if transcript_path:
        files += glob.glob(os.path.join(os.path.dirname(transcript_path), session_id or "-", "subagents", "*.jsonl"))
    msgs = {}
    for f in files:
        try:
            for line in open(f, encoding="utf-8"):
                if '"usage"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                m = r.get("message") or {}
                if r.get("type") == "assistant" and m.get("usage"):
                    msgs[(f, m.get("id") or r.get("uuid"))] = (m.get("model"), m["usage"])
        except OSError:
            pass
    t = dict.fromkeys(KEYS, 0.0)
    for model, u in msgs.values():
        if model == "<synthetic>":
            continue
        p_in, p_out, p_w5, p_w1, p_r = price_for(model)
        mult = FAST_MULT if u.get("speed") == "fast" else 1.0
        cc = u.get("cache_creation") or {}
        w1 = cc.get("ephemeral_1h_input_tokens", 0) or 0
        w_total = u.get("cache_creation_input_tokens", 0) or 0
        w5 = max(w_total - w1, 0)
        i, o, rd = u.get("input_tokens", 0) or 0, u.get("output_tokens", 0) or 0, u.get("cache_read_input_tokens", 0) or 0
        t["input"] += i
        t["output"] += o
        t["cache_write"] += w_total
        t["cache_read"] += rd
        t["cost"] += mult * (i * p_in + o * p_out + w5 * p_w5 + w1 * p_w1 + rd * p_r) / 1e6
    return t


def find_out_dir(command, cwd):
    """The output/<topic>/<date> folder a command works on (from its path args, else cwd)."""
    try:
        args = shlex.split(command)
    except ValueError:
        args = command.split()
    root = os.path.realpath(OUTPUT_ROOT)
    for a in args + [cwd]:
        if not a or a.startswith("-"):
            continue
        p = os.path.realpath(os.path.join(cwd or ".", os.path.expanduser(a)))
        if p.startswith(root + os.sep):
            parts = os.path.relpath(p, root).split(os.sep)
            if len(parts) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}$", parts[1]):
                return os.path.join(root, parts[0], parts[1])
    return None


def classify(command):
    if "ig_publish.py" in command and re.search(r"\bpost\b", command) and "--yes" in command:
        return "instagram publish"
    if "build_reel.py" in command:
        return "reel build"
    if "render.py" in command:
        return "render"
    return None


def fmt_k(n):
    return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.1f}k" if n >= 1e3 else str(int(n))


def folder_total(out_dir):
    tot, path = dict.fromkeys(KEYS, 0.0), os.path.join(out_dir, "usage.md")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            m = re.search(r"<!--usage (.*?)-->", line)
            if m:
                d = json.loads(m.group(1))
                for k in KEYS:
                    tot[k] += d.get(k, 0)
    return tot


def hook():
    data = json.load(sys.stdin)
    cmd = (data.get("tool_input") or {}).get("command", "")
    event = classify(cmd)
    if not event:
        return
    cwd = data.get("cwd") or os.getcwd()
    out_dir = find_out_dir(cmd, cwd)
    if not out_dir or not os.path.isdir(out_dir):
        return
    sid = data.get("session_id", "")
    now = session_totals(data.get("transcript_path"), sid)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    try:
        state = json.load(open(STATE))
    except (OSError, ValueError):
        state = {}
    prev = state.get(sid) or dict.fromkeys(KEYS, 0.0)
    delta = {k: max(now[k] - prev.get(k, 0), 0) for k in KEYS}
    state[sid] = now
    json.dump(state, open(STATE, "w"))

    path = os.path.join(out_dir, "usage.md")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Claude usage for this set\n\nTokens and estimated cost (Anthropic API list prices, USD) of the "
                    "Claude work since the previous logged step. On a Pro/Max subscription this is an API-equivalent "
                    "estimate.\n\n| Time | Step | Input | Output | Cache write | Cache read | Est. cost |\n"
                    "|---|---|---|---|---|---|---|\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%Y-%m-%d %H:%M')} | {event} | {fmt_k(delta['input'])} | {fmt_k(delta['output'])} | "
                f"{fmt_k(delta['cache_write'])} | {fmt_k(delta['cache_read'])} | ${delta['cost']:.2f} | "
                f"<!--usage {json.dumps({k: round(v, 4) for k, v in delta.items()})}-->\n")
    tot = folder_total(out_dir)
    tok = tot["input"] + tot["output"] + tot["cache_write"] + tot["cache_read"]
    print(json.dumps({"systemMessage": f"💰 {event}: ${delta['cost']:.2f} this step · "
                      f"{os.path.relpath(out_dir, OUTPUT_ROOT)} total ${tot['cost']:.2f} "
                      f"({fmt_k(tot['output'])} output, {fmt_k(tok)} tokens incl. cache)"}))


def report(out_dir):
    tot = folder_total(os.path.abspath(os.path.expanduser(out_dir)))
    print(f"Estimated Claude cost: ${tot['cost']:.2f}  |  input {fmt_k(tot['input'])}, output {fmt_k(tot['output'])}, "
          f"cache write {fmt_k(tot['cache_write'])}, cache read {fmt_k(tot['cache_read'])}")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "report":
            report(sys.argv[2])
        else:
            hook()
    except Exception as e:  # never break the user's workflow because of logging
        print(json.dumps({"systemMessage": f"usage_log: {e}"}))
