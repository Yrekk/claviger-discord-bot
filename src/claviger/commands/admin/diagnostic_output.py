import discord

MAX_DIAGNOSTIC_PAGE_LENGTH = 1900


def paginate_diagnostic_lines(
    lines: list[str],
    *,
    max_length: int = MAX_DIAGNOSTIC_PAGE_LENGTH,
) -> tuple[str, ...]:
    """Split diagnostic output safely below Discord's message limit."""

    if max_length <= 0:
        raise ValueError("Diagnostic page length must be greater than zero.")

    pages: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    def flush() -> None:
        nonlocal current_lines, current_length

        if not current_lines:
            return

        pages.append(
            "\n".join(
                current_lines,
            )
        )
        current_lines = []
        current_length = 0

    for line in lines:
        fragments = (
            [
                line[index : index + max_length]
                for index in range(
                    0,
                    len(line),
                    max_length,
                )
            ]
            if len(line) > max_length
            else [
                line,
            ]
        )

        for fragment in fragments:
            addition = len(fragment) + (1 if current_lines else 0)

            if current_lines and current_length + addition > max_length:
                flush()

            had_lines = bool(
                current_lines,
            )
            current_lines.append(
                fragment,
            )
            current_length += len(fragment) + (1 if had_lines else 0)

    flush()

    return tuple(
        pages,
    )


async def send_ephemeral_diagnostic(
    interaction: discord.Interaction,
    lines: list[str],
) -> None:
    """Send one or more ephemeral follow-up pages."""

    pages = paginate_diagnostic_lines(
        lines,
    )

    if not pages:
        pages = (
            "Aucune donnée de diagnostic.",
        )

    for page in pages:
        await interaction.followup.send(
            page,
            ephemeral=True,
        )
