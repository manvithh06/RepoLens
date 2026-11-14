# Every safety limit lives here so it is easy to find and change.

# GitHub reports repository size in kilobytes.
MAX_REPO_SIZE_KB = 100 * 1024  # 100 MB

GITHUB_API_TIMEOUT_SECONDS = 10.0

# Hard stop for a single `git clone`.
CLONE_TIMEOUT_SECONDS = 120.0

# How many clones may run at the same time on this server.
MAX_CONCURRENT_CLONES = 2

# Workspaces older than this are leftovers from a crash and get deleted at startup.
STALE_WORKSPACE_SECONDS = 60 * 60