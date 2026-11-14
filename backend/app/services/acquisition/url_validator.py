import re
from dataclasses import dataclass

from app.services.acquisition.exceptions import InvalidRepositoryUrl

MAX_URL_LENGTH = 300

_GITHUB_URL_PATTERN = re.compile(
    r"(?:https://)?(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9-]{0,38})/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100}?)"
    r"(?:\.git)?"
    r"(?:[/?#].*)?"
)

_URL_HELP = (
    "Enter a public GitHub repository URL, for example https://github.com/owner/repo."
)


@dataclass(frozen=True)
class RepoRef:
    """A validated owner/name pair. Every URL we use is built from these two values."""

    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def html_url(self) -> str:
        return f"https://github.com/{self.full_name}"

    @property
    def clone_url(self) -> str:
        return f"{self.html_url}.git"

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.full_name}"


def parse_github_url(raw: str) -> RepoRef:
    candidate = raw.strip()
    if not candidate or len(candidate) > MAX_URL_LENGTH:
        raise InvalidRepositoryUrl(_URL_HELP)

    match = _GITHUB_URL_PATTERN.fullmatch(candidate)
    if match is None:
        raise InvalidRepositoryUrl(_URL_HELP)

    owner, name = match["owner"], match["repo"]

    # "." and ".." would turn .../repos/owner/.. into a different API path.
    if set(name) <= {"."}:
        raise InvalidRepositoryUrl(_URL_HELP)

    return RepoRef(owner=owner, name=name)
