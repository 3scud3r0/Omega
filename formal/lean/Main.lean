import Lean.Data.Json
import Kernel

open Lean Omega

-- Parsing is outside the proven kernel. Strict bounds prevent unsupported inputs.
def parseExpr : Nat → Nat → Json → Except String Expr
  | 0, _, _ => .error "AST depth exceeds limit"
  | fuel + 1, arity, json => do
    let a ← json.getArr?
    let op ← (← json.getArrVal? 0).getStr?
    let arg (i : Nat) : Except String Json := json.getArrVal? i
    let sub (i : Nat) := do parseExpr fuel arity (← arg i)
    match op, a.size with
    | "c", 2 =>
      let b ← (← arg 1).getNat?
      if b > 1 then throw "Invalid bit"
      return .lit (b == 1)
    | "v", 2 =>
      let i ← (← arg 1).getNat?
      if i ≥ arity then throw "Variable outside domain"
      return .var i
    | "not", 2 => return .neg (← sub 1)
    | "and", 3 => return .conj (← sub 1) (← sub 2)
    | "or", 3 => return .disj (← sub 1) (← sub 2)
    | "xor", 3 => return .xor (← sub 1) (← sub 2)
    | "ite", 4 => return .ite (← sub 1) (← sub 2) (← sub 3)
    | _, _ => throw "Invalid operator or operand count"

def instructionJson : Instr → Json
  | .push b => Json.arr #[toJson "c", toJson (if b then (1 : Nat) else 0)]
  | .load i => Json.arr #[toJson "v", toJson i]
  | .neg => toJson (["not"] : List String)
  | .conj => toJson (["and"] : List String)
  | .disj => toJson (["or"] : List String)
  | .xor => toJson (["xor"] : List String)
  | .ite => toJson (["ite"] : List String)

def validate (json : Json) : Except String Json := do
  let fmt ← (← json.getObjVal? "format").getStr?
  if fmt != "omega-nextorch-certificate-1" then throw "Unsupported format"
  let task ← json.getObjVal? "task"
  let n ← (← task.getObjVal? "arity").getNat?
  if n > 12 then throw "Arity exceeds 12"
  let table ← (← task.getObjVal? "outputs").getArr?
  if table.size != 2^n then throw "Incomplete truth table"
  let e ← parseExpr 128 n (← json.getObjVal? "ast")
  let program := compile e
  if program.length > 20000 then throw "Node budget exceeded"
  let mut rows := []
  for i in [:table.size] do
    let bit ← table[i]!.getNat?
    if bit > 1 then throw "Invalid output bit"
    rows := rows ++ [((fun j => (i / 2^j) % 2 == 1), bit == 1)]
  if !check e rows then throw "Circuit rejected: truth table mismatch"
  return Json.mkObj [("valid", toJson true), ("checked_rows", toJson table.size),
    ("scope", toJson "Boolean semantics; hashes and provenance are not authenticated"),
    ("instructions", Json.arr (program.map instructionJson).toArray)]

def main (args : List String) : IO UInt32 := do
  match args with
  | [path] =>
    try
      let input ← IO.FS.readFile path
      if input.utf8ByteSize > 8000000 then
        IO.eprintln "Certificate exceeds 8 MB"
        return (1 : UInt32)
      match Json.parse input >>= validate with
      | .ok result => IO.println result.compress; return (0 : UInt32)
      | .error reason => IO.eprintln reason; return (1 : UInt32)
    catch ex =>
      IO.eprintln ex.toString
      return (1 : UInt32)
  | _ =>
    IO.eprintln "Usage: omega_kernel certificate.json"
    return (2 : UInt32)
