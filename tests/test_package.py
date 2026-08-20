def test_package_can_be_imported() -> None:
    """Verify that the project package is installed correctly."""
    import claviger

    assert claviger is not None