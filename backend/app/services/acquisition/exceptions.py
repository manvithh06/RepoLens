from app.core.errors import AppError


class InvalidRepositoryUrl(AppError):
    status_code = 400
    code = "invalid_repository_url"


class RepositoryNotFound(AppError):
    status_code = 404
    code = "repository_not_found"


class RepositoryTooLarge(AppError):
    status_code = 413
    code = "repository_too_large"


class GitHubRateLimited(AppError):
    status_code = 429
    code = "github_rate_limited"


class GitHubUnavailable(AppError):
    status_code = 502
    code = "github_unavailable"