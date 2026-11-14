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

# Limits on the files we keep for analysis.
MAX_FILE_SIZE_BYTES = 300_000  # larger files are skipped
MAX_FILE_COUNT = 5_000  # if there are more, the shallowest files are kept
MAX_WALK_ENTRIES = 50_000  # stop walking after this many folders and files

# Repository analysis.
MAX_READER_CACHE_BYTES = (
    64 * 1024 * 1024
)  # file text kept in memory during one analysis
MAX_MANIFEST_DEPTH = 3  # manifests deeper than this many folders are ignored
MAX_ENTRY_POINTS = 20
MAX_GRAPH_NODES = 150  # file graph sent to the browser; the busiest files are kept
MAX_CYCLES = 10
MAX_EXTERNAL_PACKAGES = 15
MAX_ARCHITECTURE_GROUPS = 18
MAX_ARCHITECTURE_DEPTH = 4
