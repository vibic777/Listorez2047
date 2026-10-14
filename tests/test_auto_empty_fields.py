from listorez2047.fields import Field, empty_fields, auto_page_plan, remember_applied_value, field_choice_items

def test_auto_detects_empty_and_whitespace_values():
    fields=[Field(1),Field(2),Field(3)]
    fields[0].values[4]="ok"
    fields[1].values[4]="   "
    assert [field.id for field in empty_fields(fields,4)] == [2,3]

def test_manual_correction_clears_auto_blocker():
    field=Field(1); field.values[0]="Исправлено"
    assert empty_fields([field],0) == []

def test_auto_resumes_without_reprocessing_completed_pages():
    assert auto_page_plan("saved") == "skip"
    assert auto_page_plan("skipped") == "skip"
    assert auto_page_plan("recognized") == "reuse"
    assert auto_page_plan("pending") == "recognize"
    assert auto_page_plan("error") == "recognize"

def test_field_contrast_is_portable():
    source=Field(1,contrast=2.6,preprocess_strategy="remove_lines",default_value="НЕИЗВЕСТНО")
    restored=Field.from_dict(source.portable())
    assert restored.contrast == 2.6
    assert restored.preprocess_strategy == "remove_lines"
    assert restored.default_value == "НЕИЗВЕСТНО"

def test_expression_field_with_value_does_not_block_auto():
    field=Field(1,default_value="{235:+1}",default_is_expression=True)
    field.values[0]="235"; field.statuses[0]="ok"
    assert empty_fields([field],0)==[]

def test_default_value_prefills_but_still_blocks_auto_review():
    field=Field(1,default_value="ИСПРАВЬТЕ")
    field.values[0]=field.default_value; field.statuses[0]="empty"
    assert empty_fields([field],0)==[field]

def test_two_engine_candidates_require_review():
    field=Field(1); field.values[0]="29.06.2026"; field.statuses[0]="ambiguous"
    assert empty_fields([field],0)==[field]

def test_new_field_defaults_remember_last_value():
    assert Field(1).remember_last_value is True
    assert Field.from_dict({"id": 3}).remember_last_value is True

def test_default_value_modes_are_portable():
    expression=Field(1,default_value="{505:+1#}",default_is_expression=True,remember_last_value=False)
    restored=Field.from_dict(expression.portable())
    assert restored.default_is_expression is True
    assert restored.remember_last_value is False

    remembered=Field(2,default_value="ABC",remember_last_value=True)
    restored=Field.from_dict(remembered.portable())
    assert restored.remember_last_value is True
    assert restored.default_is_expression is False

def test_remember_applied_uses_confirmed_value_not_raw_ocr():
    field=Field(1,default_value="СТАРОЕ",remember_last_value=True)
    field.candidates[0]=["OCR-СЫРОЕ"]
    field.values[0]="OCR-СЫРОЕ"
    assert field.default_value=="СТАРОЕ"
    remember_applied_value(field,"OCR-СЫРОЕ")
    remember_applied_value(field,"ИСПРАВЛЕНО")
    assert field.default_value=="ИСПРАВЛЕНО"

def test_remember_applied_ignores_empty_and_disabled_flag():
    field=Field(1,default_value="KEEP",remember_last_value=True)
    remember_applied_value(field,"   ")
    assert field.default_value=="KEEP"
    field.remember_last_value=False
    remember_applied_value(field,"NEW")
    assert field.default_value=="KEEP"

def test_choice_items_offer_scan_then_distinct_default():
    assert field_choice_items(["ABC","ABC"],"DEF")==[("scan","ABC"),("default","DEF")]
    assert field_choice_items(["ABC"],"ABC")==[("scan","ABC")]
    assert field_choice_items([],"НЕИЗВЕСТНО")==[("default","НЕИЗВЕСТНО")]
    assert field_choice_items(["","  "],"")==[]
    assert field_choice_items(["A","B"],"A")==[("scan","A"),("scan","B")]

def test_runtime_candidates_are_not_stored_in_profile():
    field=Field(1,default_value="X"); field.candidates[0]=["OCR"]
    restored=Field.from_dict(field.portable())
    assert "candidates" not in field.portable()
    assert restored.candidates=={}
