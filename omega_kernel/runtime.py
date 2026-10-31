"""Build once from source hashes; execute every request under OS isolation."""
from __future__ import annotations

from dataclasses import replace
import fcntl
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile

from omega.modules import link
from omega_native.codec import decode as decode_native
from omega_platform.budget import Budget, BUILD_BUDGET, COMPILER_BUDGET
from omega_platform.sandbox import c_tool, run as isolated_run, instrumented
from omega_security.encoding import canonical, decode
from omega_selfhost.driver import cc, compiler

from .protocol import (ARCHITECTURES, NATIVE_OPERATIONS, OMEGA_OPERATIONS,
                       envelope, elf_bytes, input_bytes, decode_execution, sha256)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT if (ROOT / "kernel/native/main.c").is_file() else ROOT / "omega_native/_sources"
CACHE = ROOT / "build/kernel"
CORE_INPUTS = ("omega_platform/budget.py", "omega_platform/sandbox.py",
               "omega_kernel/runtime.py", "omega_kernel/protocol.py",
               "omega_selfhost/bounded_rational.h")


def digest(path):
    with Path(path).open("rb") as stream:
        result = hashlib.file_digest(stream, "sha256") if hasattr(hashlib, "file_digest") else None
        if result is not None:
            return result.hexdigest()
        return sha256(stream.read())


def _input_hashes(paths):
    result = {}
    for name, path in sorted(paths.items()):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Kernel build source must be a regular nonsymlink file: " + name)
        result[name] = digest(path)
    return result


def _compile_native_chunks(linked, native_compiler, folder):
    """Bound peak stage-two memory without changing the generated C runtime.

    The existing compiler retains its whole AST/temporary arena until exit.
    Compile bounded groups of complete linked functions, then concatenate their
    declarations and bodies into ONE C translation unit. All calls keep the
    same static symbols and the same shared runtime/arena; no host expression
    compiler or second value runtime is introduced.
    """
    starts = [match.start() for match in re.finditer(r"(?m)^funcao ", linked.source)]
    if not starts or starts[0] != 0:
        raise ValueError("Canonical linked function boundaries required")
    starts.append(len(linked.source))
    groups = []
    group = ""
    for index in range(len(starts)-1):
        function = linked.source[starts[index]:starts[index+1]]
        if group and len(group) + len(function) > 12000:
            groups.append(group)
            group = ""
        group += function
    if group:
        groups.append(group)
    declarations = []
    bodies = []
    main = None
    for index, group in enumerate(groups):
        source = folder / ("part-" + str(index) + ".omega")
        output = source.with_suffix(".c")
        source.write_text(group, encoding="utf-8")
        isolated_run([native_compiler, source, output], readonly=[source], writable=[folder],
                     budget=COMPILER_BUDGET, check=True)
        lines = output.read_text(encoding="utf-8").splitlines(keepends=True)
        if lines[0] != '#include "runtime.h"\n' or not lines[-1].startswith("int main(int argc,char **argv){"):
            raise ValueError("Unexpected native compiler framing")
        if main is not None and main != lines[-1]:
            raise ValueError("Native compiler entry framing changed across groups")
        main = lines[-1]
        for line in lines[1:-1]:
            if re.fullmatch(r"static V fn_[A-Za-z0-9_]+\([^{};\n]*\);\n", line):
                declarations.append(line)
            else:
                bodies.append(line)
    result = folder / "program.c"
    result.write_text('#include "runtime.h"\n' + "".join(declarations + bodies) + main, encoding="utf-8")
    return result


def build(kind="workbench", *, diagnostic=False):
    if kind not in {"logic", "tensor", "workbench"} or type(diagnostic) is not bool:
        raise ValueError("Known kernel build kind and diagnostic boolean required")
    if kind == "workbench" and diagnostic:
        raise ValueError("Diagnostic profile currently applies to the C proof/tensor API")
    CACHE.mkdir(parents=True, exist_ok=True)
    paths = {name: ROOT / name for name in CORE_INPUTS if not name.endswith(".h")}
    paths["omega_selfhost/bounded_rational.h"] = SOURCE_ROOT / "omega_selfhost/bounded_rational.h"
    linked = None
    compiler_binary = None
    toolchain = shutil.which(os.environ.get("CC", "cc"))
    if not toolchain:
        raise RuntimeError("A C compiler is required to bootstrap this native distribution")
    paths["C-compiler-binary"] = Path(toolchain).resolve()
    if kind == "workbench":
        linked = link("kernel/omega/main.omega", SOURCE_ROOT, dynamic=True)
        compiler_binary = compiler()
        paths["Omega-compiler-binary"] = compiler_binary
        paths["Omega-bootstrap-manifest"] = compiler_binary.parent / "bootstrap.json"
        for name in ("runtime.h", "native_std.h", "memory.h"):
            paths["omega_selfhost/" + name] = ROOT / "omega_selfhost" / name
    else:
        for path in sorted((SOURCE_ROOT / "kernel/native").glob("*")):
            if path.suffix in {".h", ".c"}:
                paths[path.relative_to(SOURCE_ROOT).as_posix()] = path
    inputs = _input_hashes(paths)
    identity = {"format": "omega-kernel-build-1", "kind": kind,
                "diagnostic": diagnostic, "inputs": inputs,
                "modules": linked.manifest() if linked else None,
                "abi": platform.machine(), "compiler_argv_policy": "c11-O2-checked-v1"}
    identity_bytes = canonical(identity, max_bytes=4*1024**2, max_nodes=200000)
    subject = sha256(identity_bytes)
    target = CACHE / (kind + ("-san" if diagnostic else "") + "-" + subject[:32])
    record_path = target.with_suffix(".json")
    with (CACHE / ".build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.exists() or target.is_symlink() or record_path.exists() or record_path.is_symlink():
            if any(path.is_symlink() or not path.is_file() for path in (target, record_path)):
                raise ValueError("Kernel build cache is incomplete or redirects through a symlink")
            record = decode(record_path.read_bytes(), max_bytes=4*1024**2, max_nodes=200000)
            if (record.get("subject_sha256") != subject or record.get("identity") != identity or
                    record.get("binary_sha256") != digest(target)):
                raise ValueError("Modified kernel cache; refusing execution")
            return target
        with tempfile.TemporaryDirectory(prefix=".kernel-build-", dir=CACHE) as tmp:
            folder = Path(tmp)
            binary = folder / "program"
            if linked:
                c_source = _compile_native_chunks(linked, compiler_binary, folder)
                cc(c_source, binary)
            else:
                source = SOURCE_ROOT / "kernel/native/main.c"
                command = [toolchain, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                           "-Wno-unused-function", "-Wno-unused-parameter"]
                if diagnostic:
                    command += ["-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"]
                if kind == "tensor":
                    command += ["-DOMEGA_KERNEL_GMP=1"]
                command += [str(source), "-o", str(binary)]
                if kind == "tensor":
                    command += ["-lgmp"]
                c_tool(command, inputs=[SOURCE_ROOT / "kernel/native", SOURCE_ROOT / "omega_selfhost"],
                       output_directory=folder, budget=BUILD_BUDGET, check=True)
            record = {"identity": identity, "subject_sha256": subject,
                      "binary_sha256": digest(binary), "formal_refinement_proved": False}
            binary.replace(target)
            with record_path.open("xb") as stream:
                stream.write(canonical(record, max_bytes=4*1024**2, max_nodes=200000))
    return target


def request(operation, packet, *, budget=COMPILER_BUDGET, diagnostic=False):
    if type(budget) is not Budget:
        raise ValueError("Explicit OS budget required")
    payload = envelope(operation, packet)
    kind = "tensor" if operation in {"tensor", "graph"} else "logic"
    if operation in OMEGA_OPERATIONS:
        kind = "workbench"
        if diagnostic:
            raise ValueError("Diagnostic profile currently applies to the C proof/tensor API")
    binary = build(kind, diagnostic=diagnostic)
    with tempfile.TemporaryDirectory(prefix="omega-kernel-request-") as tmp:
        path = Path(tmp) / "request.json"
        path.write_bytes(payload)
        execute = instrumented if diagnostic else isolated_run
        result = execute([binary, path], readonly=[path], budget=budget)
    if result.timed_out or result.limit is not None:
        raise RuntimeError("Kernel execution exhausted its OS budget: " + str(result.termination))
    if operation in OMEGA_OPERATIONS:
        if not result.ok:
            raise RuntimeError("Omega kernel request failed: " + result.stderr[-2000:])
        return decode_native(result.stdout.strip())
    if result.returncode not in {0, 1, 2, 3}:
        raise RuntimeError("Native kernel terminated outside the result protocol: " + result.stderr[-2000:])
    output = decode(result.stdout.encode(), max_bytes=budget.output_bytes,
                    max_nodes=200000, max_depth=48)
    if output.get("input_sha256") != sha256(payload):
        raise ValueError("Native kernel result is not bound to this exact request")
    if bool(output.get("accepted")) != (result.returncode == 0):
        raise ValueError("Native kernel acceptance disagrees with exit status")
    if output.get("verified") and operation != "verify":
        raise ValueError("Numerical output cannot masquerade as a checked logical proof")
    return output


def execute(document, values, *, budget=Budget(), emulator=None):
    """Run emitted ELF under the same no-network sandbox as other candidates."""
    if type(budget) is not Budget:
        raise ValueError("Explicit OS budget required")
    data = elf_bytes(document)
    architecture = document["architecture"]
    native = {"AMD64": "x86_64", "arm64": "aarch64"}.get(platform.machine(), platform.machine())
    if emulator is None and architecture != native:
        raise ValueError("Cross-ISA ELF execution requires an explicit emulator path")
    arguments = input_bytes(values, len(document["parameters"]))
    with tempfile.TemporaryDirectory(prefix="omega-direct-elf-") as tmp:
        folder = Path(tmp)
        binary = folder / "program"
        binary.write_bytes(data)
        binary.chmod(0o500)
        path = folder / "input.bin"
        path.write_bytes(arguments)
        if emulator:
            emulator = Path(emulator).resolve(strict=True)
            argv = [emulator, binary, path]
            readonly = [binary, path]
        else:
            argv = [binary, path]
            readonly = [path]
        outcome = isolated_run(argv, readonly=readonly, budget=budget, threads=bool(emulator))
    if outcome.timed_out or outcome.limit is not None:
        raise RuntimeError("Direct ELF exhausted its OS execution budget")
    output = decode_execution(outcome.stdout, outcome.returncode)
    output.update({"elf_sha256": sha256(data), "input_sha256": sha256(arguments),
                   "architecture": architecture, "sandboxed": outcome.sandboxed,
                   "emulated": bool(emulator)})
    return output
