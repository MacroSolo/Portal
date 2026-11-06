import os
import sys
import time
import signal
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent
MAIN_FILE = REPO / "main.py"
BRANCH = "main"

FAST_INTERVAL = 1        # seconds between checks after an update
SLOW_INTERVAL = 15       # seconds between checks when idle
FAST_WINDOW = 3600       # stay in fast mode for 1 hour after the last update
RESTART_DELAY = 5        # min seconds between restarts if main crashes
ERROR_LOG_INTERVAL = 300 # seconds between "can't check GitHub" log lines

# Main exits with this code when the user quits (Q / Й): stop everything, no restart.
# Must match QUIT_EXIT_CODE in main.py
QUIT_EXIT_CODE = 10

# GitHub login for fetch / ls-remote: GITHUB_READ_USER / GITHUB_READ_TOKEN from config/secrets.env (a token
# with read access only); GITHUB_PUSH_USER / GITHUB_PUSH_TOKEN if those are missing. Git gets them from env
# variables through a credential helper, so the token is never in the command line or .git/config.
SECRETS_FILE = REPO / "config" / "secrets.env"
CRED_HELPER = '!f() { echo "username=$PORTAL_GIT_USER"; echo "password=$PORTAL_GIT_TOKEN"; }; f'


def log(msg):
    print(f"[autogit {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def github_login():
    """(user, token) from SECRETS_FILE, None if not there."""
    values = {}
    try:
        for line in SECRETS_FILE.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    except OSError:
        return None
    for kind in ("READ", "PUSH"):
        user, token = values.get(f"GITHUB_{kind}_USER"), values.get(f"GITHUB_{kind}_TOKEN")
        if user and token:
            if kind == "PUSH":
                log("GitHub login: GITHUB_PUSH_* from secrets.env (a read-only GITHUB_READ_* token is better here)")
            return user, token
    return None


LOGIN = github_login()


def git(*args, timeout=30):
    # Never ask for a GitHub login: without stored credentials fail at once (logged), don't wait for input
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    login = []
    if LOGIN:
        env.update(PORTAL_GIT_USER=LOGIN[0], PORTAL_GIT_TOKEN=LOGIN[1])
        login = ["-c", "credential.helper=", "-c", f"credential.helper={CRED_HELPER}"]
    return subprocess.run(["git", "-C", str(REPO), *login, *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def local_commit():
    return git("rev-parse", "HEAD").stdout.strip()


_last_error = 0.0


def remote_error(msg):
    # GitHub not reachable: logged at most every ERROR_LOG_INTERVAL, not on every check
    global _last_error
    if time.time() - _last_error > ERROR_LOG_INTERVAL:
        _last_error = time.time()
        log(f"Can't check GitHub: {msg}")


def remote_commit():
    # Only asks GitHub for the branch hash, nothing is downloaded
    try:
        result = git("ls-remote", "origin", f"refs/heads/{BRANCH}", timeout=10)
    except subprocess.TimeoutExpired:
        remote_error("git ls-remote timed out")
        return None
    if result.returncode != 0 or not result.stdout:
        remote_error(result.stderr.strip() or f"no branch {BRANCH} on origin")
        return None
    return result.stdout.split()[0]


def fetch_repo():
    # Download while main is still running, so a failed fetch doesn't stop it
    fetch = git("fetch", "origin", BRANCH, timeout=120)
    if fetch.returncode != 0:
        log(f"git fetch failed: {fetch.stderr.strip()}")
        return False
    return True


def reset_repo():
    # reset --hard instead of pull: local edits on the device can't block the update.
    # Ignored files (config/secrets.env, certs) are not touched.
    reset = git("reset", "--hard", f"origin/{BRANCH}")
    if reset.returncode != 0:
        log(f"git reset failed: {reset.stderr.strip()}")
        return False
    return True


def changed_files(old, new):
    return git("diff", "--name-only", old, new).stdout.split()


def start_main():
    log(f"Starting {MAIN_FILE.name}")
    return subprocess.Popen([sys.executable, str(MAIN_FILE)], cwd=REPO)


def stop_main(process):
    if process is None or process.poll() is not None:
        return
    log(f"Stopping {MAIN_FILE.name}")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


if __name__ == "__main__":
    # systemd / kill send SIGTERM: stop main together with autogit
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    current_process = start_main()
    last_start = time.time()
    # Start in fast mode: the device is usually rebooted right after a deploy
    fast_until = time.time() + FAST_WINDOW

    try:
        while True:
            # User quit main: full exit
            if current_process.poll() == QUIT_EXIT_CODE:
                log(f"{MAIN_FILE.name} quit by user, stopping autogit")
                break

            # Keep main running
            if current_process.poll() is not None and time.time() - last_start > RESTART_DELAY:
                log(f"{MAIN_FILE.name} exited with code {current_process.returncode}, restarting")
                current_process = start_main()
                last_start = time.time()

            # Check GitHub for a new commit
            local = local_commit()
            remote = remote_commit()
            if remote and remote != local:
                log(f"New commit {remote[:7]} (local {local[:7]}), updating")
                if not fetch_repo():
                    time.sleep(SLOW_INTERVAL)
                    continue

                stop_main(current_process)
                if reset_repo():
                    fast_until = time.time() + FAST_WINDOW
                    log(f"Updated to {remote[:7]}, fast mode for {FAST_WINDOW // 60} min")

                    # Autogit itself changed: replace this process with the new version
                    if Path(__file__).name in changed_files(local, remote):
                        log("portal_autogit.py changed, restarting autogit")
                        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])

                current_process = start_main()
                last_start = time.time()

            time.sleep(FAST_INTERVAL if time.time() < fast_until else SLOW_INTERVAL)

    except (KeyboardInterrupt, SystemExit):
        log("Stopping...")
    finally:
        stop_main(current_process)
