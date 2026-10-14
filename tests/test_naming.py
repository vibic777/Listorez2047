from listorez2047.naming import counter_value, expand_template, sanitize_filename, build_filename


def test_save_index_hash():
    fields: dict[int, str] = {}
    assert expand_template("name_{505:+1#}", fields, page_index=9, save_index=0) == "name_505"
    assert expand_template("name_{505:+1#}", fields, page_index=9, save_index=2) == "name_507"
    assert expand_template("name_{505:+1}", fields, page_index=9, save_index=0) == "name_514"


def test_page_number_is_one_plus_one():
    assert expand_template("{1:+1}", {}, 0) == "1"
    assert expand_template("{1:+1}", {}, 4) == "5"
    assert expand_template("{235:+1}", {}, 0) == "235"
    assert expand_template("{235:+1}", {}, 3) == "238"


def test_counter_template_detection():
    from listorez2047.naming import is_counter_template
    assert is_counter_template("{235:+1}")
    assert is_counter_template(" {505:+1#} ")
    assert not is_counter_template("DD.DD.DDDD")
    assert not is_counter_template("Акт_{235:+1}")
    assert not is_counter_template("")


def test_minus_times_mod():
    assert expand_template("{20:-1}", {}, 0) == "20"
    assert expand_template("{20:-1}", {}, 2) == "18"
    assert expand_template("{2:*2}", {}, 0) == "2"
    assert expand_template("{2:*2}", {}, 1) == "4"
    assert expand_template("{2:*2}", {}, 2) == "8"
    assert expand_template("{0:%10}", {}, 0) == "0"
    assert expand_template("{0:%10}", {}, 10) == "0"
    assert expand_template("{505:%10}", {}, 0) == "5"


def test_multiply_overflow_does_not_raise():
    assert counter_value(9, "*", 9, 80) is None
    assert expand_template("{9:*9}", {}, 80) == ""
    assert expand_template("{2:*2}", {}, 2) == "8"


def test_bad_expression_is_reported_not_raised():
    from listorez2047.naming import expression_issue, expand_template_safe
    assert expression_issue("") == "empty"
    assert expression_issue("{foo}") == "invalid"
    assert expression_issue("{235:+1}") is None
    assert expression_issue("Акт_{235:+1}") is None
    assert expand_template_safe("{2:*999}", {}, 50) == ""


def test_mod_zero_is_empty():
    assert counter_value(1, "%", 0, 0) is None
    assert expand_template("x_{1:%0}", {}, 0) == "x_"


def test_field_not_eaten_by_counter():
    assert expand_template("A_{1}_B_{1:+1}", {1: "154"}, 0) == "A_154_B_1"
    assert expand_template("A_{1}_B_{1:+1}", {1: "154"}, 2) == "A_154_B_3"


def test_missing_field_empty():
    assert expand_template("№{1} от {2}", {}, 0) == "№ от "


def test_sanitize():
    assert sanitize_filename("a/b:c", 3) == "a_b_c"
    assert sanitize_filename("   ", 3) == "page_3"

def test_build_filename_uses_that_page_not_a_global_cursor():
    assert build_filename("Act_{1}", {1: "22"}, 4, 0) == "Act_22.pdf"
    assert build_filename("p_{505:+1#}", {}, 9, 2) == "p_507.pdf"
