from app.serial_masking import MASK, mask_serial


def test_keeps_the_first_two_and_last_three() -> None:
    assert mask_serial("AB123456789") == "AB******789"


def test_masks_a_value_with_nothing_to_hide() -> None:
    # Two plus three is five, so a five-character serial would be shown in full.
    assert mask_serial("12345") == MASK
    assert mask_serial("AB123") == MASK


def test_six_characters_is_the_shortest_usefully_masked_value() -> None:
    assert mask_serial("123456") == "12******456"


def test_a_long_imei_is_masked_the_same_way() -> None:
    assert mask_serial("352999110123456") == "35******456"


def test_an_empty_or_missing_serial_stays_empty() -> None:
    assert mask_serial("") == ""
    assert mask_serial(None) == ""
    assert mask_serial("   ") == ""


def test_surrounding_whitespace_does_not_shift_the_visible_ends() -> None:
    assert mask_serial("  AB123456789  ") == "AB******789"


def test_the_hidden_length_never_shows() -> None:
    # Both a short and a long serial render the same width of stars.
    assert mask_serial("1234567").count("*") == mask_serial("1" * 40).count("*") == len(MASK)
