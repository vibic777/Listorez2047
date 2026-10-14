from listorez2047.pattern_dsl import normalize

def test_variable_digits_are_not_padded():
    assert normalize("22","D{1,4}") == "22"
    assert normalize("216","D{1,4}") == "216"
    assert normalize("2167","D{1,4}") == "2167"
    assert normalize("2167","D{1,3}") == "216"
    assert normalize("216","D+") == "216"

def test_drawn_digit_runs_still_pad():
    assert normalize("22","DDDD") == "0022"
    assert normalize("22","DDD") == "022"

def test_variable_letters():
    assert normalize("ЯНА","C{1,4}") == "ЯНА"
    assert normalize("ВАСЯ","C{1,4}") == "ВАСЯ"
    assert normalize("ЯНА","C+") == "ЯНА"
    assert normalize("ЯНА","CCCC") is None

def test_date_padding_regression():
    assert normalize("1.1.2024","DD.DD.DDDD") == "01.01.2024"
