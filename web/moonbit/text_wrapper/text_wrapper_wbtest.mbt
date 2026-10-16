///|
fn tokens(text : String) -> Array[String] {
  text.to_array().map(c => c.to_string())
}

///|
fn prefixes_for(widths : Array[Double]) -> Array[Double] {
  let result = [0.0]
  let mut sum = 0.0
  for width in widths {
    sum = sum + width
    result.push(sum)
  }
  result
}

///|
test "long words break at the last fitting grapheme and make progress" {
  let text = tokens("abcdefghij")
  assert_eq(wrap_starts(text, prefixes_for(Array::make(10, 1.0)), 4.0, 0), [
    0, 4, 8,
  ])
  assert_eq(wrap_starts(text, prefixes_for(Array::make(10, 1.0)), 0.0, 0), [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
  ])
  // A single oversized grapheme stays intact on its own line.
  assert_eq(wrap_starts(["👩‍💻", "a"], [0.0, 6.0, 7.0], 4.0, 0), [0, 1])
}

///|
test "CJK URL and closing punctuation use pinned upstream word opportunities" {
  assert_eq(
    wrap_starts(tokens("你好世界"), [0.0, 2.0, 4.0, 6.0, 8.0], 4.0, 0),
    [0, 2],
  )
  let url = tokens("abc/def?gh")
  assert_eq(wrap_starts(url, prefixes_for(Array::make(10, 1.0)), 5.0, 0), [
    0, 3, 7,
  ])
  assert_true(is_word("!"))
  assert_true(is_word("…"))
  assert_true(is_word("é"))
  assert_true(is_word("é"))
  assert_true(!is_word("/"))
  assert_true(!is_word("?"))
  assert_true(!is_word("你"))
}

///|
test "word boundaries retain trailing whitespace without splitting clusters" {
  let text = tokens("ab cd ef")
  assert_eq(wrap_starts(text, prefixes_for(Array::make(8, 1.0)), 4.0, 0), [
    0, 3, 6,
  ])
  let combined = ["é", "👩‍💻", "好"]
  let starts = wrap_starts(combined, [0.0, 1.0, 3.0, 5.0], 3.0, 0)
  assert_eq(starts, [0, 2])
  assert_eq(joined(combined, 0, starts[1]), "é👩‍💻")
}

///|
test "single line uses shaped-fit bypass strict affix budget and floor overflow" {
  let text = tokens("abcd")
  let widths = Array::make(4, 1.0)
  assert_eq(single_truncation_end(text, widths, 4.0, 4.0, 1.0), None)
  assert_eq(single_truncation_end(text, widths, 4.0, 3.0, 1.0), Some(1))
  assert_eq(single_truncation_end(text, widths, 4.0, 3.0, 0.0), Some(2))
  assert_eq(
    single_truncation_end(text, Array::make(4, 1.1), 4.4, 4.0, 1.0),
    None,
  )
  assert_eq(trim_end_index(tokens("a, !"), 4), 1)
}

///|
test "wrapped ellipsis and empty-affix clamps use final-line budgets" {
  let text = tokens("abcdefghij")
  let widths = Array::make(10, 1.0)
  assert_eq(wrapped_truncation_end(text, widths, 4.0, 2, 1.0), Some(7))
  assert_eq(wrapped_truncation_end(text, widths, 4.0, 2, 0.0), Some(8))
  let ellipsis = prepare_run(text, widths, prefixes_for(widths), 4.0, 4, 1.0)
  assert_eq(ellipsis.lines, ["abcd", "efg…"])
  assert_true(ellipsis.truncated)
  assert_true(ellipsis.clamped)
  let full = prepare_run(text, widths, prefixes_for(widths), 4.0, 8, 1.0)
  assert_eq(full.lines, ["abcd", "efgh", "ij"])
  assert_true(!full.truncated)
  let nowrap = prepare_run(text, widths, prefixes_for(widths), 4.0, 7, 1.0)
  assert_eq(nowrap.lines, ["abcdefghij"])
  assert_true(!nowrap.truncated)
  let long = tokens("abcdefghijklmnop")
  let long_widths = Array::make(16, 1.0)
  let three = prepare_run(
    long,
    long_widths,
    prefixes_for(long_widths),
    4.0,
    6,
    1.0,
  )
  assert_eq(three.lines, ["abcd", "efgh", "ijkl"])
  assert_true(three.truncated)
  assert_true(three.clamped)
  let word = tokens("ab cd ef gh")
  let word_widths = Array::make(word.length(), 1.0)
  let word_clamp = prepare_run(
    word,
    word_widths,
    prefixes_for(word_widths),
    4.0,
    4,
    1.0,
  )
  assert_eq(word_clamp.lines, ["ab ", "cd…"])
}

///|
test "line clamp does not truncate text that fits and limits final shaping wraps" {
  let text = tokens("abcdefgh")
  let widths = Array::make(8, 1.0)
  assert_eq(wrapped_truncation_end(text, widths, 4.0, 2, 1.0), None)
  assert_eq(
    wrap_starts(
      tokens("abcdefghijkl"),
      prefixes_for(Array::make(12, 1.0)),
      4.0,
      2,
    ),
    [0, 4],
  )
}

///|
test "frame rejects malformed and nonfinite host metrics" {
  let graphemes = fixture_texts().map(tokens)
  let advances = graphemes.map(chars => Array::make(chars.length(), 1.0))
  let prefixes = advances.map(prefixes_for)
  assert_true(valid_metrics(graphemes, advances, prefixes, [1.0, 1.0], 1.0))
  let error = "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  assert_eq(text_wrapper_frame([], [], [], [], 1.0), error)
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 0.0),
    error,
  )
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 4.1),
    error,
  )
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [0.0, 1.0], 1.0),
    error,
  )
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 0.0 / 0.0),
    error,
  )
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0 / 0.0, 1.0], 1.0),
    error,
  )
  advances[0][0] = 0.0 / 0.0
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 1.0),
    error,
  )
  advances[0][0] = 1.0
  prefixes[0][1] = 1.0 / 0.0
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 1.0),
    error,
  )
  prefixes[0][1] = 1.0
  advances[0][0] = -1.0
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 1.0),
    error,
  )
  advances[0][0] = 1.0
  prefixes[0][1] = 9.0
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 1.0),
    error,
  )
  prefixes[0][1] = 1.0
  graphemes[0][0] = "different"
  assert_eq(
    text_wrapper_frame(graphemes, advances, prefixes, [1.0, 1.0], 1.0),
    error,
  )
}

///|
test "actual element layout respects visible intrinsic minima and hidden shrink" {
  let graphemes = fixture_texts().map(tokens)
  let advances = graphemes.map(chars => Array::make(chars.length(), 8.0))
  let prefixes = advances.map(prefixes_for)
  let budgets = content_budgets(prefixes)
  assert_eq(budgets[0], 168.0)
  assert_eq(budgets[1], 80.0)
  assert_eq(budgets[2], 514.0)
  assert_eq(budgets[0] + budgets[1] + budgets[2] + 6.0 + 16.0, 784.0)
  assert_true(budgets[2] < 784.0)
  assert_eq(budgets[3], 782.0)
  assert_eq(budgets[8], 784.0)
  let runs = graphemes.mapi((i, chars) => {
    prepare_run(chars, advances[i], prefixes[i], budgets[i], i, 8.0)
  })
  for i = 0; i < 2; i = i + 1 {
    assert_eq(runs[i].lines, [fixture_texts()[i]])
    assert_true(!runs[i].truncated)
  }
  let tree = text_wrapper_tree(prefixes, runs).tree()
  assert_eq(tree.node(10).unwrap().bounds().left(), 8.0)
  assert_eq(tree.node(10).unwrap().bounds().top(), 8.0)
  assert_eq(tree.node(20).unwrap().bounds().top(), 44.0)
  assert_eq(tree.node(1400).unwrap().bounds().left(), 9.0)
  assert_eq(tree.node(1400).unwrap().bounds().top(), 45.0)
  assert_eq(
    tree.node(1501).unwrap().bounds().top() -
    tree.node(1500).unwrap().bounds().top(),
    32.0,
  )
  let frame = text_wrapper_frame(graphemes, advances, prefixes, [8.0, 8.0], 1.0)
  assert_true(frame.has_prefix("{\"ok\":true"))
  // gpui::green() is HSL(120,100%,25%), not bright CSS lime.
  assert_true(frame.contains("\"border\":\"#008000\""))
  assert_true(!frame.contains("#00ff00"))
}

///|
test "fractional measured widths ceil before visible automatic minimum limits" {
  let graphemes = fixture_texts().map(tokens)
  let advances = graphemes.map(chars => Array::make(chars.length(), 8.03))
  let prefixes = advances.map(prefixes_for)
  let budgets = content_budgets(prefixes)
  assert_eq(budgets[0], 169.0)
  assert_eq(budgets[1], 81.0)
  assert_eq(budgets[2], 512.0)
  assert_eq(budgets[0] + budgets[1] + budgets[2] + 6.0 + 16.0, 784.0)
  let runs = graphemes.mapi((i, chars) => {
    prepare_run(chars, advances[i], prefixes[i], budgets[i], i, 8.03)
  })
  let tree = text_wrapper_tree(prefixes, runs).tree()
  for i = 0; i < 2; i = i + 1 {
    assert_eq(runs[i].lines, [fixture_texts()[i]])
    assert_true(!runs[i].truncated)
    assert_eq(
      tree.node((11 + i).to_uint64()).unwrap().bounds().size().width(),
      budgets[i] + 2.0,
    )
  }
  assert_eq(tree.node(13).unwrap().bounds().size().width(), budgets[2] + 2.0)
}
