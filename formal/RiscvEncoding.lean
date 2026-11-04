import Mathlib.Data.Nat.Basic
import Lean.Elab.Tactic.Omega
import Mathlib.Tactic.NormNum

/-! Bit-exact ADDI field and little-endian encoding. These formulas match the
RV64 emitter's positive-immediate branch, and extend its previous abstract
instruction model to bytes. Parsing, register allocation and ELF loading are
not implied by this local round-trip theorem. -/
namespace OmegaRiscvEncoding
def encodeAddi (rd rs : Fin 32) (imm : Fin 2048) : Nat :=
  19 + rd.val*128 + rs.val*32768 + imm.val*1048576
def opcode (w : Nat) : Nat := w%128
def destination (w : Nat) : Nat := (w/128)%32
def function3 (w : Nat) : Nat := (w/4096)%8
def source (w : Nat) : Nat := (w/32768)%32
def immediate (w : Nat) : Nat := w/1048576

theorem encode_decode (rd rs : Fin 32) (imm : Fin 2048) :
    opcode (encodeAddi rd rs imm) = 19 ∧
    destination (encodeAddi rd rs imm) = rd.val ∧
    function3 (encodeAddi rd rs imm) = 0 ∧
    source (encodeAddi rd rs imm) = rs.val ∧
    immediate (encodeAddi rd rs imm) = imm.val := by
  have hr := rd.isLt
  have hs := rs.isLt
  have hi := imm.isLt
  unfold opcode destination function3 source immediate encodeAddi
  omega

def bytesLE (w : Nat) : List Nat :=
  [w%256, (w/256)%256, (w/65536)%256, (w/16777216)%256]
def wordLE : List Nat → Option Nat
  | [a,b,c,d] => some (a+b*256+c*65536+d*16777216)
  | _ => none

theorem bytes_roundtrip (w : Nat) (bounded : w < 4294967296) :
    wordLE (bytesLE w) = some w := by
  change some (w%256 + (w/256)%256*256 + (w/65536)%256*65536 +
    (w/16777216)%256*16777216) = some w
  congr 1
  have h0 := Nat.mod_add_div w 256
  have h1 := Nat.mod_add_div (w/256) 256
  have h2 := Nat.mod_add_div (w/65536) 256
  have h3 := Nat.mod_add_div (w/16777216) 256
  simp only [Nat.div_div_eq_div_mul] at h1 h2 h3
  norm_num at h1 h2 h3
  omega

theorem instruction_bytes_roundtrip (rd rs : Fin 32) (imm : Fin 2048) :
    wordLE (bytesLE (encodeAddi rd rs imm)) = some (encodeAddi rd rs imm) := by
  apply bytes_roundtrip
  have hr := rd.isLt
  have hs := rs.isLt
  have hi := imm.isLt
  unfold encodeAddi
  omega
#print axioms encode_decode
#print axioms bytes_roundtrip
#print axioms instruction_bytes_roundtrip
end OmegaRiscvEncoding
