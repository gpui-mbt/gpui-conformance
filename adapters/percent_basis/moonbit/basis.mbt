///| Percent ratios are passed untouched to the production API, not resolved here.
fn basis(value : Json) -> @layout.FlexBasis {
  match value {
    Null => @layout.FlexBasis::auto()
    Number(value, ..) => checked(@layout.FlexBasis::points(value))
    Object(fields) => {
      if fields.length() != 1 {
        abort("unsupported flex_basis encoding")
      }
      checked(@layout.FlexBasis::percent(number(fields.get("percent").unwrap())))
    }
    _ => abort("unsupported flex_basis encoding")
  }
}
