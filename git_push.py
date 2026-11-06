"""
Push to GitHub using GITHUB_PUSH_USER / GITHUB_PUSH_TOKEN from config/secrets.env.
DEVELOPMENT ONLY: devices must not have push credentials.

Usage:
    python git_push.py                  # push current branch to origin
    python git_push.py origin main      # push given remote and branch
    python git_push.py --env path/to/secrets.env
"""
import os
import sys
import subprocess
from pathlib import Path

from config import load_env

REPO = Path(__file__).resolve().parent
ENV_FILE = REPO / "config" / "secrets.env"

# Git reads the credentials from env variables, so the token never appears
# in the command line, shell history or .git/config
CRED_HELPER = '!f() { echo "username=$GITHUB_PUSH_USER"; echo "password=$GITHUB_PUSH_TOKEN"; }; f'


def main(args):
    env_file = ENV_FILE
    if "--env" in args:
        i = args.index("--env")
        env_file = Path(args[i + 1])
        args = args[:i] + args[i + 2:]

    if not env_file.exists():
        sys.exit(f"Not found: {env_file}")

    secrets = load_env(env_file)
    missing = [k for k in ("GITHUB_PUSH_USER", "GITHUB_PUSH_TOKEN") if not secrets.get(k)]
    if missing:
        sys.exit(f"Empty in {env_file}: {', '.join(missing)}")

    remote = args[0] if len(args) > 0 else "origin"
    branch = args[1] if len(args) > 1 else subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()

    env = os.environ | {
        "GITHUB_PUSH_USER": secrets["GITHUB_PUSH_USER"],
        "GITHUB_PUSH_TOKEN": secrets["GITHUB_PUSH_TOKEN"],
        "GIT_TERMINAL_PROMPT": "0",  # fail instead of asking for a password
    }
    cmd = ["git", "-c", "credential.helper=", "-c", f"credential.helper={CRED_HELPER}",
           "push", remote, branch]

    print(f"Pushing {branch} -> {remote} as {secrets['GITHUB_PUSH_USER']}", flush=True)
    result = subprocess.run(cmd, cwd=REPO, env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main(sys.argv[1:])
