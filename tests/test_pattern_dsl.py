from listorez2047.pattern_dsl import find_all, normalize, parse


def test_hex_soft_dots():
    pattern = "HH.HH.HHHH"
    assert normalize("AB.0F.FFCC", pattern) == "AB.0F.FFCC"
    assert normalize("AB,0F,FFCC", pattern) == "AB.0F.FFCC"
    assert normalize("AB 0F FFCC", pattern) == "AB.0F.FFCC"
    assert normalize("AB0FFFCC", pattern) == "AB.0F.FFCC"
    assert normalize("AB·0F·FFCC", pattern) == "AB.0F.FFCC"


def test_hex_delete_separators():
    assert normalize("AB.0F.FFCC", "HH[*>]HH[*>]HHHH") == "AB0FFFCC"
    assert normalize("AB.0F.FFCC", r"HH[*\d]HH[*\d]HHHH") == "AB0FFFCC"


def test_canonicalize_alias():
    assert normalize("AB,0F,FFCC", r"HH[*\c=.]HH[*\c=.]HHHH") == "AB.0F.FFCC"
    assert normalize("AB,0F,FFCC", "HH[*>.]HH[*>.]HHHH") == "AB.0F.FFCC"


def test_date_pad():
    assert normalize("1.1.2024", "DD.DD.DDDD") == "01.01.2024"
    assert normalize("01,01,99", "DD.DD.DDDD") == "01.01.0099"


def test_class_digits():
    assert normalize("№154", "{0-9}") == "154"
    assert "154" in find_all("act 154 done", "{0-9}")


def test_hh_lower():
    assert normalize("AB.FF5", "hh.HHH") == "ab.FF5"


def test_hex_case_modes():
    assert normalize("ab0f", "HHHH") == "AB0F"
    assert normalize("AB0F", "hhhh") == "ab0f"
    assert normalize("Ab0F", "XXXX") == "Ab0F"


def test_letter_case_modes():
    assert normalize("Акт", "CCC") == "Акт"
    assert normalize("Акт", "UUU") == "АКТ"
    assert normalize("Акт", "LLL") == "акт"


def test_invalid_patterns_do_not_raise():
    from listorez2047.pattern_dsl import find_all, pattern_issue, normalize
    assert find_all("235", "[unclosed") == []
    assert find_all("235", "{unclosed") == []
    assert find_all("abc", "{235:+1}") == []
    assert pattern_issue("{235:+1}") == "counter"
    assert pattern_issue("[unclosed") == "invalid"
    assert pattern_issue("DD.DD.DDDD") is None
    assert normalize("xx", "[") is None


def test_parse_hex_slots():
    slots = parse("HH.HH.HHHH")
    kinds = [type(s).__name__ for s in slots]
    assert kinds == ["DataSlot", "SepSlot", "DataSlot", "SepSlot", "DataSlot"]
