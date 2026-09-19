import pytest

from claviger.commands.admin.diagnostic_output import paginate_diagnostic_lines


def test_diagnostic_output_splits_long_results_without_losing_lines() -> None:
    """Keep large scans below Discord's message limit."""

    pages = paginate_diagnostic_lines(
        [
            "header",
            "a" * 12,
            "b" * 12,
        ],
        max_length=15,
    )

    assert len(pages) == 3
    assert pages[0] == "header"
    assert pages[1] == "a" * 12
    assert pages[2] == "b" * 12


def test_diagnostic_output_rejects_invalid_page_length() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        paginate_diagnostic_lines(
            [],
            max_length=0,
        )
