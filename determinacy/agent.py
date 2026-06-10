"""Shell out to the user's SOTA coding agent. The agent command reads the prompt on
stdin and prints its response on stdout (e.g. `codex exec -`, `claude -p`).

We assume the caller has such an agent; this module is the only place the tool talks
to a model, so swapping agents is a one-line config change.
"""
import shlex, subprocess, json


def run_agent(agent_cmd, prompt, timeout=600):
    try:
        p = subprocess.run(shlex.split(agent_cmd), input=prompt,
                           capture_output=True, text=True, timeout=timeout)
        return p.stdout or ""
    except Exception as e:
        return f"__AGENT_ERROR__ {e}"


def extract_json(text):
    """Parse the last {...} block from agent output; None on failure."""
    if not text or "{" not in text or "}" not in text:
        return None
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:
        return None
