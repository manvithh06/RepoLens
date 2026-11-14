import pytest

from app.services.acquisition.exceptions import InvalidRepositoryUrl
from app.services.acquisition.url_validator import parse_github_url


@pytest.mark.parametrize(
    ("raw", "owner", "name"),
    [
        ("https://github.com/octocat/hello-world", "octocat", "hello-world"),
        ("https://github.com/octocat/hello-world/", "octocat", "hello-world"),
        ("https://github.com/octocat/hello-world.git", "octocat", "hello-world"),
        ("github.com/octocat/hello-world", "octocat", "hello-world"),
        ("https://www.github.com/octocat/hello-world", "octocat", "hello-world"),
        ("  https://github.com/octocat/hello-world  ", "octocat", "hello-world"),
        (
            "https://github.com/octocat/hello-world/tree/main/src",
            "octocat",
            "hello-world",
        ),
        ("https://github.com/octocat/hello-world?tab=readme", "octocat", "hello-world"),
        (
            "https://github.com/octocat/octocat.github.io",
            "octocat",
            "octocat.github.io",
        ),
    ],
)
def test_accepts_valid_urls(raw: str, owner: str, name: str) -> None:
    ref = parse_github_url(raw)
    assert (ref.owner, ref.name) == (owner, name)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not a url",
        "http://github.com/octocat/hello-world",
        "https://gitlab.com/octocat/hello-world",
        "https://github.com.evil.com/octocat/hello-world",
        "https://github.com@evil.com/octocat/hello-world",
        "https://evil.com/github.com/octocat/hello-world",
        "file:///etc/passwd",
        "https://github.com/octocat",
        "https://github.com/octocat/..",
        "https://github.com/octocat/.",
        "https://github.com/octocat/../other",
        "https://github.com/-bad/repo",
        "https://github.com/octocat/repo name",
        "https://github.com/octocat/hello-world\nextra",
        "https://github.com/" + "a" * 40 + "/repo",
        "https://github.com/octocat/" + "a" * 400,
    ],
)
def test_rejects_invalid_urls(raw: str) -> None:
    with pytest.raises(InvalidRepositoryUrl):
        parse_github_url(raw)


def test_built_urls_come_from_validated_parts() -> None:
    ref = parse_github_url("https://github.com/octocat/hello-world/tree/main?x=1")
    assert ref.html_url == "https://github.com/octocat/hello-world"
    assert ref.clone_url == "https://github.com/octocat/hello-world.git"
    assert ref.api_url == "https://api.github.com/repos/octocat/hello-world"
