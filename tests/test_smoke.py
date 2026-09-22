def test_package_importable():
    import bot

    assert bot.__name__ == "bot"
