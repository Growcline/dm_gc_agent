# growcline_dm_agent

A standalone Claude Code agent that makes **Growcline** creatives (static posts, carousels, reels) with the Growcline brand kit. It needs nothing from `~/dm_agent`.

## Install (Ubuntu / WSL2)
```bash
git clone git@github.com:Growcline/dm_gc_agent.git
cd dm_gc_agent && bash install.sh
```
It installs missing tools (`python3`, `python3-venv`, `ffmpeg`, `wkhtmltopdf`, emoji font; asks for your sudo password), creates the reel venv (`~/.local/share/growcline_dm_agent/venv`, linked as `.venv`), links the folder as `~/growcline_dm_agent`, asks for the delivery folder (a Windows `C:\...` path is fine on WSL), optionally makes the agent available in every folder, and renders a test post. Safe to re-run.
Options: `--delivery-dir PATH`, `--global-agent` / `--no-global-agent`, `--yes` (no prompts), `--skip-apt`.
Claude Code itself: `curl -fsSL https://claude.ai/install.sh | bash`, then run `claude` once and log in.

## Run
```bash
cd ~/growcline_dm_agent
claude --agent growcline_dm_agent
```
Then ask, e.g. *"static post: DevOps myth vs reality"*, *"5-slide carousel on SAP ABAP careers"*, *"30 s reel for the Java Full Stack course"*.
A plain `claude` session in this folder follows the same rules (see `CLAUDE.md`).

## What's here
| Path | Contents |
|---|---|
| `.claude/agents/growcline_dm_agent.md` | the agent: scope, Growcline rules, spec format, render → footer check → QA → caption → deliver, reel pipeline |
| `.claude/settings.json` | hook: logs tokens + estimated cost per set into `output/<topic>/<date>/usage.md` |
| `brand/` | Growcline kit: `brand.json` (colours, Nunito font, logo, red footer bar), `client.md` (approved claims, rules, confirmed facts), logo, fonts, licensed stock photos |
| `scripts/` | `render.py`, `check_footer.py`, `build_reel.py`, `make_music.py`, `deliver.sh`, `usage_log.py` |
| `references/` | copy guide, motion-graphics template, `example-spec.json` (the approved DevOps Myth vs Reality post) |
| `install.sh` | installer (see above) |
| `config.env` | `DELIVERY_DIR`: finished sets are copied to `<DELIVERY_DIR>/growcline/<topic>/<date>/` |
| `output/` | finished sets |
| `.venv` | link to a Python venv with `requirements.txt` (edge-tts, numpy, pillow), needed for reels |

Publishing to Instagram is not part of this agent.
