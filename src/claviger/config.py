import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

SUPPORTED_ENVIRONMENTS = frozenset(
    {
        "development",
        "production",
    }
)

DEFAULT_SELECTOR_PATH = Path(".env")


def _normalize_environment(
    value: str | None,
) -> str:
    """Validate and normalize a Claviger runtime environment name."""

    if value is None or not value.strip():
        raise RuntimeError(
            "CLAVIGER_ENV is missing. Select either 'development' or 'production'."
        )

    environment = value.strip().lower()

    if environment not in SUPPORTED_ENVIRONMENTS:
        supported = ", ".join(
            sorted(SUPPORTED_ENVIRONMENTS),
        )

        raise RuntimeError(
            f"Unsupported CLAVIGER_ENV '{environment}'. Expected one of: {supported}."
        )

    return environment


def _load_selected_environment(
    selector_path: Path,
) -> tuple[str, bool]:
    """
    Resolve the runtime environment.

    CLAVIGER_ENV provided by the operating system takes precedence. This is
    intended for containers and managed deployment environments.

    Otherwise, the local .env file acts only as an environment selector.
    """

    runtime_environment = os.getenv(
        "CLAVIGER_ENV",
    )

    if runtime_environment is not None:
        return (
            _normalize_environment(
                runtime_environment,
            ),
            False,
        )

    if not selector_path.is_file():
        raise RuntimeError(
            f"Environment selector '{selector_path}' is missing. "
            "Create it with CLAVIGER_ENV=development or "
            "CLAVIGER_ENV=production."
        )

    selector_values = dotenv_values(
        selector_path,
    )

    unexpected_keys = sorted(key for key in selector_values if key != "CLAVIGER_ENV")

    if unexpected_keys:
        keys = ", ".join(
            unexpected_keys,
        )

        raise RuntimeError(
            f"Environment selector '{selector_path}' must contain only "
            f"CLAVIGER_ENV. Move these settings to the environment-specific "
            f"file instead: {keys}."
        )

    environment = _normalize_environment(
        selector_values.get(
            "CLAVIGER_ENV",
        )
    )

    return environment, True


def _load_environment_values(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> tuple[str, dict[str, str]]:
    """
    Load the configuration belonging to the selected runtime environment.

    Local development uses .env as a selector and reads values exclusively
    from .env.development or .env.production.

    When CLAVIGER_ENV is supplied directly by the operating system, runtime
    environment variables are allowed to override file values. This supports
    containerized deployments without requiring environment files inside the
    image.
    """

    environment, selected_from_file = _load_selected_environment(
        selector_path,
    )

    environment_path = selector_path.with_name(
        f".env.{environment}",
    )

    file_values: dict[str, str] = {}

    if environment_path.is_file():
        raw_values = dotenv_values(
            environment_path,
        )

        declared_environment = _normalize_environment(
            raw_values.get(
                "CLAVIGER_ENV",
            )
        )

        if declared_environment != environment:
            raise RuntimeError(
                f"Environment file '{environment_path}' declares "
                f"CLAVIGER_ENV={declared_environment}, but "
                f"{environment} was selected."
            )

        file_values = {
            key: value for key, value in raw_values.items() if value is not None
        }

    elif selected_from_file:
        raise RuntimeError(
            f"Configuration file '{environment_path}' is missing "
            f"for the selected '{environment}' environment."
        )

    if selected_from_file:
        return environment, file_values

    runtime_values = {
        **file_values,
        **os.environ,
    }

    return environment, runtime_values


def _get_required_value(
    values: Mapping[str, str],
    name: str,
    environment: str,
) -> str:
    """Return one required non-empty configuration value."""

    value = values.get(
        name,
    )

    if value is None or not value.strip():
        raise RuntimeError(f"{name} is missing for the '{environment}' environment.")

    return value.strip()


def _get_required_positive_int(
    values: Mapping[str, str],
    name: str,
    environment: str,
) -> int:
    """Return one required positive integer configuration value."""

    raw_value = _get_required_value(
        values,
        name,
        environment,
    )

    try:
        value = int(
            raw_value,
        )

    except ValueError as error:
        raise RuntimeError(
            f"{name} must be a valid integer for the '{environment}' environment."
        ) from error

    if value <= 0:
        raise RuntimeError(
            f"{name} must be greater than zero for the '{environment}' environment."
        )

    return value


def _get_optional_positive_int(
    values: Mapping[str, str],
    name: str,
    environment: str,
) -> int | None:
    """Return one optional positive integer configuration value."""

    raw_value = values.get(
        name,
    )

    if raw_value is None or not raw_value.strip():
        return None

    try:
        value = int(
            raw_value,
        )

    except ValueError as error:
        raise RuntimeError(
            f"{name} must be a valid integer for the '{environment}' environment."
        ) from error

    if value <= 0:
        raise RuntimeError(
            f"{name} must be greater than zero for the '{environment}' environment."
        )

    return value


def get_environment_name(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> str:
    """Return the explicitly selected Claviger runtime environment."""

    environment, _ = _load_environment_values(
        selector_path,
    )

    return environment


def get_discord_token(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> str:
    """Return the Discord bot token for the selected environment."""

    environment, values = _load_environment_values(
        selector_path,
    )

    return _get_required_value(
        values,
        "DISCORD_TOKEN",
        environment,
    )


def get_discord_bot_user_id(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> int:
    """Return the expected Discord bot user ID for the selected environment."""

    environment, values = _load_environment_values(
        selector_path,
    )

    return _get_required_positive_int(
        values,
        "DISCORD_BOT_USER_ID",
        environment,
    )


def get_discord_guild_id(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> int:
    """Return the Discord guild ID for the selected environment."""

    environment, values = _load_environment_values(
        selector_path,
    )

    return _get_required_positive_int(
        values,
        "DISCORD_GUILD_ID",
        environment,
    )


def get_database_path(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> str:
    """Return the explicit SQLite database path for the selected environment."""

    environment, values = _load_environment_values(
        selector_path,
    )

    return _get_required_value(
        values,
        "DATABASE_PATH",
        environment,
    )


def get_error_report_forum_id(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> int:
    """Return the Discord forum receiving runtime error reports."""

    environment, values = _load_environment_values(
        selector_path,
    )

    new_value = values.get(
        "ERROR_REPORT_FORUM_ID",
    )

    legacy_value = values.get(
        "ADMIN_REPORT_FORUM_ID",
    )

    if (
        (new_value is None or not new_value.strip())
        and legacy_value is not None
        and legacy_value.strip()
    ):
        raise RuntimeError(
            "ADMIN_REPORT_FORUM_ID is obsolete. Rename it to ERROR_REPORT_FORUM_ID."
        )

    return _get_required_positive_int(
        values,
        "ERROR_REPORT_FORUM_ID",
        environment,
    )


def get_activity_report_forum_id(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> int | None:
    """Return the optional Discord forum receiving activity reports."""

    environment, values = _load_environment_values(
        selector_path,
    )

    return _get_optional_positive_int(
        values,
        "ACTIVITY_REPORT_FORUM_ID",
        environment,
    )


def get_admin_commands_channel_id(
    selector_path: Path = DEFAULT_SELECTOR_PATH,
) -> int | None:
    """Return the optional Discord channel dedicated to admin commands."""

    environment, values = _load_environment_values(
        selector_path,
    )

    return _get_optional_positive_int(
        values,
        "ADMIN_COMMANDS_CHANNEL_ID",
        environment,
    )
