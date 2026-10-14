from listorez2047.profiles import convert_page_value

def test_custom_page_unit_examples():
    assert convert_page_value(210,"mm","cm") == 21
    assert round(convert_page_value(25.4,"mm","in"),6) == 1
    inches=convert_page_value(297,"mm","in")
    assert round(convert_page_value(inches,"in","mm"),6) == 297
