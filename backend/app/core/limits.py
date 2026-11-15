from dataclasses import dataclass

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
LLM_MAX_RETRY_WAIT_SECONDS = 20.0  # a longer Retry-After fails at once instead
LLM_RETRY_WAIT_SECONDS = 2.0  # when the provider gives no Retry-After
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


@dataclass(frozen=True)
class LLMBudget:
    """How much repository text one tour or chat answer may send to the model."""

    tour_files: int
    tour_file_chars: int
    tour_folders: int
    max_tokens_file: int
    max_tokens_folder: int
    max_tokens_repo: int
    chat_snippets: int
    chat_snippet_chars: int
    max_tokens_chat: int
    concurrency: int


# Hugging Face Inference Providers: the original limits.
HF_BUDGET = LLMBudget(
    tour_files=MAX_TOUR_FILES,
    tour_file_chars=MAX_TOUR_FILE_CHARS,
    tour_folders=MAX_TOUR_FOLDERS,
    max_tokens_file=LLM_MAX_TOKENS_FILE,
    max_tokens_folder=LLM_MAX_TOKENS_FOLDER,
    max_tokens_repo=LLM_MAX_TOKENS_REPO,
    chat_snippets=CHAT_TOP_K,
    chat_snippet_chars=2_500,
    max_tokens_chat=LLM_MAX_TOKENS_CHAT,
    concurrency=LLM_CONCURRENCY,
)

# OpenAI-compatible endpoints such as Groq. Sized for a free tier of about 8,000
# tokens per minute: a whole tour is roughly 8 calls and 12,000 tokens.
COMPACT_BUDGET = LLMBudget(
    tour_files=5,
    tour_file_chars=2_500,
    tour_folders=2,
    max_tokens_file=500,
    max_tokens_folder=350,
    max_tokens_repo=2_000,
    chat_snippets=5,
    chat_snippet_chars=1_500,
    max_tokens_chat=900,
    concurrency=2,
)

# Per-IP rate limits on the expensive endpoints: (requests, window in seconds).
RATE_LIMIT_ANALYZE = (10, 10 * 60)
RATE_LIMIT_TOUR = (10, 10 * 60)
RATE_LIMIT_CHAT = (40, 10 * 60)
