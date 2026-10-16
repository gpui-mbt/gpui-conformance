///|
test "typing, caret movement, selection, undo and redo stay in TextField" {
  input_reset()
  assert_true(input_insert("abc"))
  assert_eq(input_text(), "abc")
  assert_eq(input_head(), 3)
  assert_true(input_key("ArrowLeft", false, false, false))
  assert_eq(input_head(), 2)
  assert_true(input_key("ArrowRight", true, false, false))
  assert_eq(input_anchor(), 2)
  assert_eq(input_head(), 3)
  assert_eq(input_copy(), "c")
  assert_true(input_cut())
  assert_eq(input_text(), "ab")
  assert_true(input_can_undo())
  assert_true(input_key("z", false, true, false))
  assert_eq(input_text(), "abc")
  assert_true(input_can_redo())
  assert_true(input_key("z", true, true, false))
  assert_eq(input_text(), "ab")
}

///|
test "UTF16 caret indices account for supplementary code points" {
  input_reset()
  assert_true(input_insert("a😀漢"))
  assert_eq(input_head(), 4)
  assert_true(input_key("ArrowLeft", false, false, false))
  assert_eq(input_head(), 3)
  assert_true(input_key("ArrowLeft", false, false, false))
  assert_eq(input_head(), 1)
  assert_true(input_key("ArrowLeft", true, false, false))
  assert_eq(input_anchor(), 1)
  assert_eq(input_head(), 0)
  assert_eq(input_copy(), "a")
}

///|
test "composition preview, cancellation, commit and undo preserve original range" {
  input_reset()
  assert_true(input_insert("abc"))
  assert_true(input_key("a", false, true, false))
  assert_eq(input_anchor(), 0)
  assert_eq(input_head(), 3)
  assert_true(input_preedit("にほん", 3, 3))
  assert_true(input_composing())
  assert_eq(input_marked_start(), 0)
  assert_eq(input_marked_end(), 3)
  assert_eq(input_text(), "にほん")
  assert_true(input_finish("", false))
  assert_false(input_composing())
  assert_eq(input_text(), "abc")
  assert_eq(input_anchor(), 0)
  assert_eq(input_head(), 3)
  assert_true(input_preedit("かな", 2, 2))
  assert_true(input_finish("日本", true))
  assert_eq(input_text(), "日本")
  assert_eq(input_marked_start(), -1)
  assert_true(input_can_undo())
  assert_true(input_key("z", false, true, false))
  assert_eq(input_text(), "abc")
}

///|
test "surrogate-interior IME selection is rejected without changing state" {
  input_reset()
  assert_true(input_insert("Z"))
  assert_false(input_preedit("😀", 1, 1))
  assert_false(input_composing())
  assert_eq(input_text(), "Z")
}
