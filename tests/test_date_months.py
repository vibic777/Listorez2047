from listorez2047.pattern_dsl import normalize

def test_month_words_and_digits():
    cases = {
        "01 июня 2026":"01.06.2026", "1 июня 2026":"01.06.2026",
        "29 июнь 2026":"29.06.2026", "29 ИЮНЬ. 2026":"29.06.2026",
        "01.06.2026":"01.06.2026", "01/06/2026":"01.06.2026",
        "01 June 2026":"01.06.2026", "1-го июля 2026 г":"01.07.2026",
    }
    for source, expected in cases.items(): assert normalize(source,"DD.M.DDDD") == expected

def test_month_separator_and_mm_sugar():
    assert normalize("01 июня 2026","DD-M-DDDD") == "01-06-2026"
    assert normalize("01 June 2026","DD.MM.DDDD") == "01.06.2026"

def test_old_numeric_date_is_unchanged():
    assert normalize("01 июня 2026","DD.DD.DDDD") != "01.06.2026"
    assert normalize("1.1.2024","DD.DD.DDDD") == "01.01.2024"

def test_invalid_month_is_rejected():
    assert normalize("01 foo 2026","DD.M.DDDD") is None
    assert normalize("01.13.2026","DD.M.DDDD") is None
    assert normalize("01.².2026","DD.M.DDDD") is None

def test_every_russian_month_word_is_mapped_without_ocr_digit_confusion():
    words=("января","февраля","марта","апреля","мая","июнь","июля","августа","сентября","октября","ноября","декабря")
    for number,word in enumerate(words,1):
        assert normalize(f"29 {word} 2026","DD.M.DDDD")==f"29.{number:02d}.2026"
