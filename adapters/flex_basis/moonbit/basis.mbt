///| The historical point profile deliberately has no Percent API dependency.
fn basis(value : Json) -> @layout.FlexBasis {
  match value {
    Null => @layout.FlexBasis::auto()
    Number(value, ..) => checked(@layout.FlexBasis::points(value))
    _ => abort("unsupported flex_basis encoding")
  }
}
