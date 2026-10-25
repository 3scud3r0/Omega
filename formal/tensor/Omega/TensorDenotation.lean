import Omega.Types
namespace OmegaFormal
def denote : {t : Ty} → Term t → Value t
  | _, .number q => q
  | _, .matrix a => a
  | _, .add a b => addValue (denote a) (denote b)
  | _, .matmul a b => multiply (denote a) (denote b)
  | _, .relu a => if 0 < denote a then denote a else 0
end OmegaFormal
