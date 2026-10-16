///|
test "actual upstream primality algorithm and half-open chunk boundaries" {
  for n in [0, 1, 4, 6, 9, 25, 49, 121, 100000000] { assert_false(is_prime(n)) }
  for n in [2, 3, 5, 7, 11, 97, 99999989] { assert_true(is_prime(n)) }
  assert_eq(hello_web_count(0, 100), 25)
  assert_eq(hello_web_count(0, 10000), 1229)
  assert_eq(hello_web_count(2, 3), 1)
  assert_eq(hello_web_count(3, 3), 0)
  assert_eq(hello_web_count(-1, 4), -1)
  assert_eq(hello_web_count(0, 100000001), -1)
  let mut sum = 0
  for i = 0; i < 12; i = i + 1 {
    sum = sum + hello_web_count(i * 833, if i == 11 { 10000 } else { (i + 1) * 833 })
  }
  assert_eq(sum, 1229)
  assert_eq(number(0), "0")
  assert_eq(number(10000000), "10,000,000")
}

///|
test "chunk lifecycle rejects stale duplicate invalid and post-completion results" {
  hello_web_init(4)
  let s = state.val
  let _ = start(s)
  assert_true(running(s))
  assert_eq(s.run_limit, 10000000)
  assert_false(hello_web_receive(0, 0, 1, 1))
  assert_false(hello_web_receive(1, 12, 1, 1))
  assert_false(hello_web_receive(1, 0, 833334, 1))
  assert_false(hello_web_receive(1, 0, -1, 1))
  assert_true(hello_web_receive(1, 0, 2, 1))
  assert_false(hello_web_receive(1, 0, 2, 1))
  assert_eq(start(s), "{\"action\":\"none\"}")
  for i = 1; i < 12; i = i + 1 { assert_true(hello_web_receive(1, i, i, 200)) }
  assert_false(running(s))
  assert_eq(s.total, 68)
  assert_eq(s.history.length(), 1)
  assert_false(hello_web_receive(1, 11, 1, 200))
  s.selected = 2
  assert_eq(status(s), "Found 68 primes below 10,000,000 in 200 ms")
  let _ = start(s)
  assert_eq(s.generation, 2)
  assert_eq(s.run_limit, 100000000)
  assert_false(hello_web_receive(1, 0, 2, 300))
  hello_web_fail(1)
  assert_false(s.failed)
  hello_web_fail(2)
  assert_true(s.failed)
  assert_false(hello_web_receive(2, 0, 2, 300))
  assert_eq(start(s), "{\"action\":\"none\"}")
}

///|
test "real ElementTree hit targets govern preset and start controls" {
  hello_web_init(8)
  let widths = [220.0, 250.0, 110.0, 30.0, 30.0, 40.0, 90.0, 300.0]
  let _ = hello_web_frame(widths, 1.0)
  let tree = last_tree.val.unwrap()
  let button = tree.node(24).unwrap().bounds()
  assert_eq(hello_web_click(button.left() + 3.0, button.top() + 3.0), "{\"action\":\"select\"}")
  assert_eq(state.val.selected, 1)
  let _ = hello_web_frame(widths, 1.0)
  let go = last_tree.val.unwrap().node(26).unwrap().bounds()
  let _ = hello_web_click(go.left() + 3.0, go.top() + 3.0)
  assert_true(running(state.val))
  assert_eq(state.val.run_limit, 50000000)
  assert_eq(hello_web_click(button.left() + 3.0, button.top() + 3.0), "{\"action\":\"none\"}")
  assert_eq(state.val.selected, 1)
  assert_eq(hello_web_click(-1.0, 3.0), "{\"action\":\"none\"}")
  assert_eq(hello_web_frame([], 1.0), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  assert_eq(hello_web_frame(widths, 0.0), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
}
