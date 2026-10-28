import Lean.Data.Json
import ProofPrelude
import OperationalSemantics
open Lean OmegaTensor

def cellsCount (shape : List Nat) : Nat := shape.foldl (· * ·) 1

structure Parameter where
  name : String
  shape : List Nat
  offset : Nat
  node : Nat
  initial : Nat
  deriving Inhabited
structure TensorCode where
  shape : List Nat
  cells : Array OmegaTensor.Expr
  deriving Inhabited
instance : Inhabited OmegaTensor.Expr := ⟨.lit 0⟩

def qread (j : Json) : Except String ℚ := do
  let s ← j.getStr?
  if s.length > 10000 then throw "Rational text exceeds budget"
  match s.splitOn "/" with
  | [a] =>
    let some n := a.toInt? | throw "Invalid rational numerator"
    return n
  | [a,b] =>
    let some n := a.toInt? | throw "Invalid numerator"
    let some d := b.toInt? | throw "Invalid denominator"
    if d = 0 then throw "Zero denominator"
    return Rat.divInt n d
  | _ => throw "Invalid rational"

def shapeRead (j : Json) : Except String (List Nat) := do
  let a ← j.getArr?
  if a.size > 2 then throw "Tensor rank exceeds two"
  let shape ← a.toList.mapM Json.getNat?
  if shape.any (fun n => n = 0 || n > 2048) || (cellsCount shape) > 1000000 then
    throw "Invalid tensor dimensions"
  return shape

def tensorRead : List Nat → Json → Except String (List ℚ)
  | [], j => return [← qread j]
  | n :: ns, j => do
    let a ← j.getArr?
    if a.size != n then throw "State tensor has wrong shape"
    return (← a.toList.mapM (tensorRead ns)).flatten

def parameters (ir : Json) : Except String (List Parameter) := do
  let nodes ← (← ir.getObjVal? "nos").getArr?
  let raw ← (← ir.getObjVal? "parametros").getArr?
  let mut result := []
  let mut offset := 0
  for p in raw do
    let name ← (← p.getObjVal? "nome").getStr?
    if result.any (fun x : Parameter => x.name = name) then throw "Duplicate parameter"
    let node ← (← p.getObjVal? "id").getNat?
    let initial ← (← p.getObjVal? "inicial").getNat?
    if !(initial < node && node < nodes.size) then throw "Invalid parameter indices"
    let item := nodes[node]!
    if (← (← item.getObjVal? "op").getStr?) != "param" ||
       (← (← item.getObjVal? "nome").getStr?) != name then throw "Parameter signature mismatch"
    let shape ← shapeRead (← item.getObjVal? "forma")
    result := result ++ [⟨name, shape, offset, node, initial⟩]
    offset := offset + (cellsCount shape)
    if offset > 1000000 then throw "Coordinate budget exceeded"
  return result

def stateRead (params : List Parameter) (state : Json) : Except String (List ℚ) := do
  let entries ← state.getObj?
  if entries.toArray.size != params.length then throw "Parameter set mismatch"
  let mut values := []
  for p in params do
    values := values ++ (← tensorRead p.shape (← state.getObjVal? p.name))
  return values

def makeCode (shape : List Nat) (cells : Array OmegaTensor.Expr) : Except String TensorCode := do
  if (cellsCount shape) != cells.size then throw "Scalarization shape mismatch"
  return ⟨shape,cells⟩

def scalarize (ir : Json) (params : List Parameter) : Except String (Array TensorCode) := do
  if (← (← ir.getObjVal? "formato").getStr?) != "omega-ir-2" then throw "Unsupported IR"
  let nodes ← (← ir.getObjVal? "nos").getArr?
  if nodes.isEmpty || nodes.size > 12000 then throw "Invalid graph size"
  let mut codes := #[]
  for i in [:nodes.size] do
    let node := nodes[i]!
    let op ← (← node.getObjVal? "op").getStr?
    let shape ← shapeRead (← node.getObjVal? "forma")
    let refs ← (← (← node.getObjVal? "args").getArr?).toList.mapM Json.getNat?
    if refs.any (· ≥ i) then throw "Forward or invalid graph reference"
    let args := refs.map (fun r => codes[r]!)
    let a := args[0]?.getD default
    let b := args[1]?.getD default
    let mut cells := #[]
    if op = "num" then
      if !refs.isEmpty || !shape.isEmpty then throw "Invalid literal shape"
      cells := #[.lit (← qread (← node.getObjVal? "v"))]
    else if op = "param" then
      if !refs.isEmpty then throw "Parameter has operands"
      let name ← (← node.getObjVal? "nome").getStr?
      let some p := params.find? (fun p => p.name = name && p.node = i) | throw "Unbound parameter"
      if shape != p.shape || codes[p.initial]!.shape != shape then throw "Parameter initializer mismatch"
      cells := (List.range (cellsCount shape)).toArray.map (fun j => .var (p.offset+j))
    else if op = "zeros" || op = "identidade" then
      if !refs.isEmpty || shape.isEmpty then throw "Invalid constructor"
      if op = "identidade" && (shape.length != 2 || shape[0]! != shape[1]!) then throw "Invalid identity shape"
      cells := (List.range (cellsCount shape)).toArray.map (fun j =>
        .lit (if op = "identidade" && j / shape[0]! = j % shape[0]! then 1 else 0))
    else if op = "stack" then
      if args.isEmpty || args.any (fun x => x.shape != a.shape) ||
         shape != refs.length :: a.shape then throw "Invalid stack shape"
      cells := (args.map (·.cells)).foldl (· ++ ·) #[]
    else if ["neg","relu","soma","transposta"].contains op then
      if refs.length != 1 then throw "Unary arity mismatch"
      if op = "neg" || op = "relu" then
        if shape != a.shape then throw "Unary shape mismatch"
        cells := a.cells.map (fun x => if op = "neg" then .neg x else .relu x)
      else if op = "soma" then
        if !shape.isEmpty then throw "Sum must be scalar"
        cells := #[sumExpr a.cells.toList]
      else
        if a.shape.length != 2 || shape != [a.shape[1]!,a.shape[0]!] then throw "Invalid transpose"
        cells := (List.range (cellsCount shape)).toArray.map (fun j =>
          a.cells[(j % shape[1]!) * a.shape[1]! + j / shape[1]!]!)
    else
      if refs.length != 2 then throw "Binary arity mismatch"
      if op = "+" || op = "-" then
        if a.shape != b.shape || shape != a.shape then throw "Addition shape mismatch"
        cells := (List.range (cellsCount shape)).toArray.map (fun j =>
          if op = "+" then .add a.cells[j]! b.cells[j]! else .add a.cells[j]! (.neg b.cells[j]!))
      else if op = "*" || op = "/" then
        if op = "*" && !a.shape.isEmpty && !b.shape.isEmpty then throw "Tensor times tensor"
        if op = "/" && !b.shape.isEmpty then throw "Tensor denominator"
        if shape != (if a.shape.isEmpty then b.shape else a.shape) then throw "Scale shape mismatch"
        cells := (List.range (cellsCount shape)).toArray.map (fun j =>
          let x := a.cells[if a.shape.isEmpty then 0 else j]!
          let y := b.cells[if b.shape.isEmpty then 0 else j]!
          if op = "*" then .mul x y else .div x y)
      else if op = "^" then
        if !shape.isEmpty || !a.shape.isEmpty || !b.shape.isEmpty ||
           (← (← nodes[refs[1]!]!.getObjVal? "op").getStr?) != "num" then throw "Invalid exponent"
        let q ← qread (← nodes[refs[1]!]!.getObjVal? "v")
        if q.den != 1 || q.num < 0 || q.num > 20 then throw "Exponent outside 0..20"
        cells := #[.pow a.cells[0]! q.num.toNat]
      else if op = "dot" then
        if !shape.isEmpty || a.shape.length != 1 || a.shape != b.shape then throw "Invalid dot product"
        cells := #[sumExpr ((List.range a.cells.size).map (fun j => .mul a.cells[j]! b.cells[j]!))]
      else if op = "@" then
        if a.shape.length != 2 || !(b.shape.length = 1 || b.shape.length = 2) ||
           a.shape[1]! != b.shape[0]! then throw "Invalid matrix product"
        let cols := if b.shape.length = 1 then 1 else b.shape[1]!
        if shape != (if b.shape.length = 1 then [a.shape[0]!] else [a.shape[0]!,cols]) then
          throw "Matrix output shape mismatch"
        cells := (List.range (cellsCount shape)).toArray.map (fun j =>
          sumExpr ((List.range a.shape[1]!).map (fun k =>
            .mul a.cells[(j / cols) * a.shape[1]! + k]! b.cells[k * cols + j % cols]!)))
      else throw "Unsupported graph operator"
    codes := codes.push (← makeCode shape cells)
  return codes

structure MT where
  state : Array UInt32
  index : Nat

def seedMT (seed : UInt32) : MT := Id.run do
  let mut a := Array.replicate 624 (0 : UInt32)
  a := a.set! 0 19650218
  for i in [1:624] do
    a := a.set! i ((1812433253 : UInt32) * (a[i-1]! ^^^ (a[i-1]! >>> 30)) + UInt32.ofNat i)
  let mut i := 1
  for _ in [:624] do
    a := a.set! i ((a[i]! ^^^ ((a[i-1]! ^^^ (a[i-1]! >>> 30))*1664525)) + seed)
    i := i+1
    if i ≥ 624 then
      a := a.set! 0 a[623]!
      i := 1
  for _ in [:623] do
    a := a.set! i ((a[i]! ^^^ ((a[i-1]! ^^^ (a[i-1]! >>> 30))*1566083941)) - UInt32.ofNat i)
    i := i+1
    if i ≥ 624 then
      a := a.set! 0 a[623]!
      i := 1
  a := a.set! 0 0x80000000
  return ⟨a,624⟩

def nextMT (mt : MT) : UInt32 × MT := Id.run do
  let mut a := mt.state
  let mut index := mt.index
  if index ≥ 624 then
    for i in [:624] do
      let y := (a[i]! &&& 0x80000000) ||| (a[(i+1)%624]! &&& 0x7fffffff)
      a := a.set! i (a[(i+397)%624]! ^^^ (y >>> 1) ^^^ (if y &&& 1 = 1 then 0x9908b0df else 0))
    index := 0
  let mut y := a[index]!
  y := y ^^^ (y >>> 11)
  y := y ^^^ ((y <<< 7) &&& 0x9d2c5680)
  y := y ^^^ ((y <<< 15) &&& 0xefc60000)
  y := y ^^^ (y >>> 18)
  return (y, ⟨a,index+1⟩)

def noiseMT (count : Nat) (seed : Nat) (rate : ℚ) : List ℚ := Id.run do
  let mut state := seedMT (UInt32.ofNat seed)
  let mut result := []
  for _ in [:count] do
    let mut n := 3
    while n ≥ 3 do
      let (x,next) := nextMT state
      state := next
      n := (x >>> 30).toNat
    result := result ++ [rate * ((n : ℚ)-1) / 16]
  return result

def verifyCertificate (cert : Json) : Except String Unit := do
  let kind ← (← cert.getObjVal? "tipo").getStr?
  if kind != "gradiente_ir" && kind != "passo_ir" then throw "Unsupported certificate kind"
  let ir ← cert.getObjVal? "ir"
  let params ← parameters ir
  let codes ← scalarize ir params
  let loss ← (← cert.getObjVal? "perda").getStr?
  let lid ← (← (← ir.getObjVal? "perdas").getObjVal? loss).getNat?
  if lid ≥ codes.size || !codes[lid]!.shape.isEmpty then throw "Invalid loss reference"
  let e := codes[lid]!.cells[0]!
  let before ← stateRead params (← cert.getObjVal? "estado_antes")
  let grad ← stateRead params (← cert.getObjVal? "gradientes")
  for code in codes do
    if code.cells.any (fun x => !defined (environment before) x) then throw "Undefined primal expression"
  if !checkGradient e before grad then throw "Gradient rejected by formal kernel"
  if kind = "gradiente_ir" then return ()
  let after ← stateRead params (← cert.getObjVal? "estado_depois")
  let policy ← (← cert.getObjVal? "politica").getStr?
  if !["passo","passo_livre","passo_ruidoso"].contains policy then throw "Invalid step policy"
  let target ← (← cert.getObjVal? "alvo").getStr?
  let some parameter := params.find? (·.name = target) | throw "Unknown update target"
  let rate ← qread (← cert.getObjVal? "taxa")
  let commands ← (← ir.getObjVal? "comandos").getArr?
  let mut authorized := false
  let seed := (cert.getObjVal? "semente" >>= Json.getNat?).toOption.getD 0
  if seed ≥ 4294967296 then throw "Seed outside UInt32"
  for c in commands do
    let op ← (← c.getObjVal? "tipo").getStr?
    if op = policy then
      let name ← (← c.getObjVal? "nome").getStr?
      let selected ← (← c.getObjVal? "parametro").getStr?
      let rid ← (← c.getObjVal? "taxa").getNat?
      if rid ≥ codes.size || !codes[rid]!.shape.isEmpty then throw "Invalid rate reference"
      let matchSeed := if policy = "passo_ruidoso" then
        (c.getObjVal? "semente" >>= Json.getNat?).toOption = some seed else true
      if name = loss && selected = target && matchSeed &&
         eval (environment before) codes[rid]!.cells[0]! = rate then authorized := true
  if !authorized then throw "Step not authorized by an IR instruction"
  let targets := (List.range (cellsCount parameter.shape)).map (parameter.offset + ·)
  let values := if policy = "passo_ruidoso" then noiseMT targets.length seed rate else
    List.replicate targets.length (0 : ℚ)
  let noise := (List.range before.length).map (fun i =>
    if parameter.offset ≤ i && i < parameter.offset + (cellsCount parameter.shape) then values[i-parameter.offset]! else 0)
  if !checkStep e before after grad noise targets rate (policy = "passo") then throw "Step rejected by formal kernel"
  if (← qread (← cert.getObjVal? "perda_antes")) != eval (environment before) e ||
     (← qread (← cert.getObjVal? "perda_depois")) != eval (environment after) e then
    throw "Recorded loss mismatch"

def modifyJson (j : Json) (key : String) (value : Json) : Except String Json := do
  let fields ← j.getObj?
  return Json.mkObj (fields.toArray.toList.map (fun p =>
    (p.1, if p.1 = key then value else p.2)))

def localRule (node : Json) (nodes : Array Json) : Except String (Option (String × Nat)) := do
  let op ← (← node.getObjVal? "op").getStr?
  let args ← (← (← node.getObjVal? "args").getArr?).toList.mapM Json.getNat?
  let literal (i : Nat) (q : ℚ) : Except String Bool := do
    if (← (← nodes[i]!.getObjVal? "op").getStr?) != "num" then return false
    return (← qread (← nodes[i]!.getObjVal? "v")) = q
  if op = "+" then
    if ← literal args[0]! 0 then return some ("add_zero",args[1]!)
    if ← literal args[1]! 0 then return some ("add_zero",args[0]!)
  if op = "-" then
    if ← literal args[1]! 0 then return some ("sub_zero",args[0]!)
    let inner := nodes[args[0]!]!
    if (← (← inner.getObjVal? "op").getStr?) = "+" then
      let nested ← (← inner.getObjVal? "args").getArr?
      if nested.size = 2 && (← nested[1]!.getNat?) = args[1]! then
        return some ("add_cancel_right", ← nested[0]!.getNat?)
  if op = "+" then
    let inner := nodes[args[0]!]!
    if (← (← inner.getObjVal? "op").getStr?) = "-" then
      let nested ← (← inner.getObjVal? "args").getArr?
      if nested.size = 2 && (← nested[1]!.getNat?) = args[1]! then
        return some ("sub_cancel_right", ← nested[0]!.getNat?)
  if op = "*" then
    if ← literal args[0]! 1 then return some ("mul_one",args[1]!)
    if ← literal args[1]! 1 then return some ("mul_one",args[0]!)
  if op = "/" then
    if ← literal args[1]! 1 then return some ("div_one",args[0]!)
  if op = "^" then
    if ← literal args[1]! 1 then return some ("pow_one",args[0]!)
  if ["neg","transposta","relu"].contains op then
    let inner := nodes[args[0]!]!
    if (← (← inner.getObjVal? "op").getStr?) = op then
      if op = "relu" then return some ("relu_idem",args[0]!)
      let sub ← (← inner.getObjVal? "args").getArr?
      let target ← sub[0]!.getNat?
      return some ((if op = "neg" then "double_neg" else "double_transpose"),target)
  return none

def verifyOptimization (cert : Json) (allowSynth : Bool := false) : Except String Unit := do
  let format ← (← cert.getObjVal? "formato").getStr?
  if format != "omega-opt-cert-1" && !(allowSynth && format = "omega-opt-cert-2") then throw "Invalid optimization format"
  let old ← cert.getObjVal? "original"
  let new ← cert.getObjVal? "otimizado"
  let oldParams ← parameters old
  let newParams ← parameters new
  let _ ← scalarize old oldParams
  let _ ← scalarize new newParams
  let oldNodes ← (← old.getObjVal? "nos").getArr?
  let newNodes ← (← new.getObjVal? "nos").getArr?
  let mapping ← (← (← cert.getObjVal? "mapeamento").getArr?).toList.mapM Json.getNat?
  let proofs ← (← cert.getObjVal? "regras").getArr?
  if mapping.length != oldNodes.size || proofs.size > mapping.length then throw "Invalid optimization map"
  let mut used := []
  for proof in proofs do
    let index ← (← proof.getObjVal? "indice").getNat?
    if index ≥ oldNodes.size || used.contains index then throw "Duplicate rewrite index"
    used := index :: used
  let mut pos := 0
  for i in [:oldNodes.size] do
    let node := oldNodes[i]!
    let args ← (← (← node.getObjVal? "args").getArr?).toList.mapM Json.getNat?
    let mapped := args.map (fun j => mapping[j]!)
    if mapped.any (· ≥ pos) then throw "Invalid rewrite dependency"
    let clone ← modifyJson node "args" (toJson mapped)
    let entry := proofs.find? (fun p =>
      (p.getObjVal? "indice" >>= Json.getNat?).toOption = some i)
    match entry with
    | some proof =>
      let target ← (← proof.getObjVal? "resultado").getNat?
      if allowSynth && format = "omega-opt-cert-2" then
        if mapping[i]! != target then throw "Synthesized map witness mismatch"
      else
        let some (rule,expected) ← localRule clone (newNodes.extract 0 pos) | throw "Unrecognized rewrite"
        if (← (← proof.getObjVal? "regra").getStr?) != rule || expected != target || mapping[i]! != target then
          throw "Rewrite witness mismatch"
      if target ≥ pos || (← node.getObjVal? "forma").compress !=
         (← newNodes[target]!.getObjVal? "forma").compress then throw "Rewrite changes shape"
    | none =>
      if mapping[i]! != pos || pos ≥ newNodes.size || clone.compress != newNodes[pos]!.compress then
        throw "Unproved graph change"
      pos := pos+1
  if pos != newNodes.size then throw "Extra optimized nodes"
  for label in ["simbolos","perdas"] do
    let entries ← (← old.getObjVal? label).getObj?
    let mut expected := []
    for p in entries.toArray do
      let i ← p.2.getNat?
      if i ≥ mapping.length then throw "Invalid table reference"
      expected := (p.1,toJson mapping[i]!) :: expected
    if (Json.mkObj expected).compress != (← new.getObjVal? label).compress then throw "Unproved symbol remapping"
  let params ← (← old.getObjVal? "parametros").getArr?
  let mut expectedParams := #[]
  for p in params do
    let id ← (← p.getObjVal? "id").getNat?
    let initial ← (← p.getObjVal? "inicial").getNat?
    let p ← modifyJson p "id" (toJson mapping[id]!)
    let p ← modifyJson p "inicial" (toJson mapping[initial]!)
    expectedParams := expectedParams.push p
  if (Json.arr expectedParams).compress != (← new.getObjVal? "parametros").compress then throw "Parameter remapping mismatch"
  let commands ← (← old.getObjVal? "comandos").getArr?
  let mut expectedCommands := #[]
  for c in commands do
    match (c.getObjVal? "taxa" >>= Json.getNat?).toOption with
    | some i =>
      if i ≥ mapping.length then throw "Invalid rate reference"
      expectedCommands := expectedCommands.push (← modifyJson c "taxa" (toJson mapping[i]!))
    | none => expectedCommands := expectedCommands.push c
  if (Json.arr expectedCommands).compress != (← new.getObjVal? "comandos").compress then
    throw "Command remapping mismatch"

def verifyDocument (doc : Json) : Except String (Nat × Nat) := do
  let format ← (← doc.getObjVal? "format").getStr?
  if format = "omega-native-optimization-2" then
    verifyOptimization (← doc.getObjVal? "optimization")
    return (0,0)
  if format != "omega-native-result-2" then throw "Invalid result format"
  let ir ← doc.getObjVal? "ir"
  match (doc.getObjVal? "optimization").toOption with
  | some cert =>
    verifyOptimization cert
    if (← cert.getObjVal? "otimizado").compress != ir.compress then throw "Optimized execution graph mismatch"
  | none => pure ()
  let params ← parameters ir
  let codes ← scalarize ir params
  let initial ← stateRead params (← doc.getObjVal? "initial_state")
  let final ← stateRead params (← doc.getObjVal? "state")
  let mut expected := List.replicate initial.length (0 : ℚ)
  for p in params do
    let code := codes[p.initial]!
    for j in [:code.cells.size] do
      if !defined (environment expected) code.cells[j]! then throw "Undefined initializer"
      expected := expected.set (p.offset+j) (eval (environment expected) code.cells[j]!)
  if initial != expected then throw "Initial state does not match the source initializers"
  let symbols ← (← ir.getObjVal? "simbolos").getObj?
  let observed ← doc.getObjVal? "values"
  if (← observed.getObj?).toArray.size != symbols.toArray.size then throw "Observed symbol set mismatch"
  for entry in symbols.toArray do
    let index ← entry.2.getNat?
    if index ≥ codes.size then throw "Invalid symbol reference"
    let code := codes[index]!
    let values ← tensorRead code.shape (← observed.getObjVal? entry.1)
    for j in [:code.cells.size] do
      if !defined (environment final) code.cells[j]! ||
         eval (environment final) code.cells[j]! != values[j]! then throw "Observed native value is incorrect"
  let commands ← (← ir.getObjVal? "comandos").getArr?
  let mut expectedCommands := #[]
  for c in commands do
    let kind ← (← c.getObjVal? "tipo").getStr?
    if ["gradiente","gradientes","passo","passo_livre","passo_ruidoso"].contains kind then
      expectedCommands := expectedCommands.push c
  let allCerts ← (← doc.getObjVal? "certificates").getArr?
  let identities := allCerts.filter (fun c =>
    (c.getObjVal? "tipo" >>= Json.getStr?).toOption = some "identidade_nativa")
  let certs := allCerts.filter (fun c =>
    (c.getObjVal? "tipo" >>= Json.getStr?).toOption != some "identidade_nativa")
  let mut expectedIdentities := #[]
  for c in commands do
    if (c.getObjVal? "tipo" >>= Json.getStr?).toOption = some "reescrever" &&
       (c.getObjVal? "left").isOk then
      expectedIdentities := expectedIdentities.push (Json.mkObj
        [("tipo",toJson "identidade_nativa"),("left",← c.getObjVal? "left"),("right",← c.getObjVal? "right")])
  for c in commands do
    let kind ← (← c.getObjVal? "tipo").getStr?
    if kind = "provar" || kind = "teorema" then
      expectedIdentities := expectedIdentities.push (Json.mkObj
        [("tipo",toJson "identidade_nativa"),("left",← c.getObjVal? "left"),("right",← c.getObjVal? "right")])
  if (Json.arr identities).compress != (Json.arr expectedIdentities).compress then
    throw "Universal certificates do not match the source proof commands"
  if certs.size != expectedCommands.size then throw "Missing or extra execution certificates"
  let mut current := initial
  for i in [:certs.size] do
    let c := certs[i]!
    if (← c.getObjVal? "ir").compress != ir.compress then throw "Certificate graph differs from the executed graph"
    let before ← stateRead params (← c.getObjVal? "estado_antes")
    if before != current then throw "Execution certificate chain is broken"
    let expectedCommand := expectedCommands[i]!
    if (← (← c.getObjVal? "perda").getStr?) !=
       (← (← expectedCommand.getObjVal? "nome").getStr?) then throw "Certificate loss does not match instruction"
    let kind ← (← c.getObjVal? "tipo").getStr?
    let instruction ← (← expectedCommand.getObjVal? "tipo").getStr?
    if instruction.startsWith "passo" then
      if kind != "passo_ir" || (← (← c.getObjVal? "politica").getStr?) != instruction ||
         (← (← c.getObjVal? "alvo").getStr?) !=
         (← (← expectedCommand.getObjVal? "parametro").getStr?) then throw "Step instruction mismatch"
      let rid ← (← expectedCommand.getObjVal? "taxa").getNat?
      if rid ≥ codes.size || (← qread (← c.getObjVal? "taxa")) !=
         eval (environment before) codes[rid]!.cells[0]! then throw "Step rate mismatch"
      if instruction = "passo_ruidoso" then
        let seed ← (← c.getObjVal? "semente").getNat?
        if seed != (← (← expectedCommand.getObjVal? "semente").getNat?) then throw "Instruction seed mismatch"
    else if kind != "gradiente_ir" then throw "Gradient instruction mismatch"
    verifyCertificate c
    if kind = "passo_ir" then current ← stateRead params (← c.getObjVal? "estado_depois")
  if current != final then throw "Final state differs from the verified execution chain"
  return (certs.size,identities.size)

def exprSource : OmegaTensor.Expr → String
  | .lit q => s!"(.lit (({q.num} : ℚ) / {q.den}))"
  | .var i => s!"(.var {i})"
  | .add a b => s!"(.add {exprSource a} {exprSource b})"
  | .neg a => s!"(.neg {exprSource a})"
  | .mul a b => s!"(.mul {exprSource a} {exprSource b})"
  | .div a b => s!"(.div {exprSource a} {exprSource b})"
  | .pow a n => s!"(.pow {exprSource a} {n})"
  | .relu a => s!"(.relu {exprSource a})"
  | .gate a b => s!"(.gate {exprSource a} {exprSource b})"

def optimizationProof (cert : Json) (allowSynth : Bool := false) : Except String String := do
  verifyOptimization cert allowSynth
  let old ← cert.getObjVal? "original"
  let new ← cert.getObjVal? "otimizado"
  let oldCodes ← scalarize old (← parameters old)
  let newCodes ← scalarize new (← parameters new)
  let mapping ← (← (← cert.getObjVal? "mapeamento").getArr?).toList.mapM Json.getNat?
  let mut result := "import ProofPrelude\nnamespace OmegaOptimizationProof\nopen OmegaTensor\nset_option maxRecDepth 10000\nset_option maxHeartbeats 4000000\n"
  for i in [:oldCodes.size] do
    let target := mapping[i]!
    if oldCodes[i]!.cells.size != newCodes[target]!.cells.size then throw "Optimization coordinate mismatch"
    for j in [:oldCodes[i]!.cells.size] do
      let a := exprSource oldCodes[i]!.cells[j]!
      let b := exprSource newCodes[target]!.cells[j]!
      result := result ++ s!"theorem value_{i}_{j} (s : Env) : eval s {a} = eval s {b} := by\n  simp only [eval] <;> (try split_ifs) <;> simp_all <;> ring\n#print axioms value_{i}_{j}\n"
      result := result ++ s!"theorem gradient_{i}_{j} (s : Env) (x : Nat) : eval s (derive {a} x) = eval s (derive {b} x) := by\n  simp only [derive, eval] <;> (try split_ifs) <;> simp_all <;> ring\n#print axioms gradient_{i}_{j}\n"
      if allowSynth then
        result := result ++ s!"theorem domain_{i}_{j} (s : Env) : defined s {a} = defined s {b} := by\n  simp [defined, eval]\n#print axioms domain_{i}_{j}\n"
  return result ++ "end OmegaOptimizationProof\n"

def main (args : List String) : IO UInt32 := do
  match args with
  | ["--prove-map", file, output] =>
    try
      let input ← IO.FS.readFile file
      let parsed := Json.parse input
      match parsed >>= (fun cert => optimizationProof cert true) with
      | .ok proof => IO.FS.writeFile output proof; return (0 : UInt32)
      | .error error => IO.eprintln error; return (1 : UInt32)
    catch error => IO.eprintln error.toString; return (1 : UInt32)
  | ["--prove-opt", file, output] =>
    try
      let input ← IO.FS.readFile file
      match Json.parse input >>= optimizationProof with
      | .error reason => IO.eprintln reason; return (1 : UInt32)
      | .ok proof => IO.FS.writeFile output proof; return (0 : UInt32)
    catch e => IO.eprintln e.toString; return (1 : UInt32)
  | [file] =>
    try
      let text ← IO.FS.readFile file
      if text.utf8ByteSize > 64000000 then IO.eprintln "File exceeds 64 MB"; return (1 : UInt32)
      match Json.parse text >>= verifyDocument with
      | .error reason => IO.eprintln reason; return (1 : UInt32)
      | .ok count => IO.println (Json.mkObj [("valid",toJson true),("certificates",toJson count.1),("universal_identities",toJson count.2)]).compress; return (0 : UInt32)
    catch e => IO.eprintln e.toString; return (1 : UInt32)
  | _ => IO.eprintln "usage: omega_tensor_kernel native-result.json"; return (2 : UInt32)
