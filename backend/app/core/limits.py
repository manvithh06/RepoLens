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

# Analyses kept in memory after the clone is deleted (for the tour and chat).
ANALYSIS_TTL_SECONDS = 60 * 60
MAX_STORED_ANALYSES = 20
MAX_STORED_ANALYSIS_BYTES = (
    40 * 1024 * 1024
)  # text kept per analysis (chunks, excerpts)

# Guided tour (LLM). Every call is capped.
LLM_TIMEOUT_SECONDS = 90.0
LLM_CONCURRENCY = 4
MAX_TOUR_FILES = 12
MAX_TOUR_FILE_CHARS = 6_000
MAX_TOUR_FOLDERS = 8
LLM_MAX_TOKENS_FILE = 1_200
LLM_MAX_TOKENS_FOLDER = 1_000
LLM_MAX_TOKENS_REPO = 3_000
TOUR_CACHE_SECONDS = 6 * 60 * 60
MAX_CACHED_TOURS = 50

# Repository chat (BM25 retrieval over chunks kept in memory).
MAX_STORED_TOTAL_BYTES = 200 * 1024 * 1024  # all stored analyses together
CHUNK_WINDOW_LINES = 60
CHUNK_OVERLAP_LINES = 10
MAX_CHUNK_LINES = 120  # longer functions and classes are split into windows
MAX_CHUNKS_PER_FILE = 40
MAX_CHAT_CHUNKS = 8_000
CHAT_TOP_K = 8
CHAT_MIN_SCORE = 1.0  # below this BM25 score nothing relevant was found
LLM_MAX_TOKENS_CHAT = 2_000
MAX_CHAT_QUESTION_CHARS = 1_000
MAX_CHAT_HISTORY = 6
