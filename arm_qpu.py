#!/usr/bin/env python3
"""Run an AArch64 binary on a quantum stored-program (von Neumann) processor.

    python3 arm_qpu.py prog.c --entry factor --args 91            # compiles with clang or gcc first
    python3 arm_qpu.py prog.o --entry factor --args 91 [--mem=1,2,3] [--config config.json]

The same machine code runs on a CPU (Unicorn AArch64 emulator, as reference) and on the
quantum interpreter circuit (backend from config.json: simulator | aer | ibm). A report
(Markdown + JSON) lists unsupported instructions, resources and the CPU/QPU comparison.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qcpu.a64 import check, disassemble, ALL_CLASSES, MEMOPS
from qcpu.loader import load_program
from qcpu.machine import Config, QuantumARM
from qcpu.bitsim import simulate, value
from qcpu.reference import run_reference, layout, DATA_BASE, CODE_BASE

DEFAULTS = {
    "backend": "simulator",          # simulator | aer | ibm
    "register_width": "auto",        # W: bits per register; auto = smallest W >= 8 the code layout allows
    "registers": "auto",             # auto | all | [0, 1, 2, ...]
    "memory_words": "auto",          # data memory cells (4 bytes each); auto = 2^(W-4) if the code uses memory
    "max_steps": "auto",             # auto = number of steps the CPU reference needs
    "isa": "full",                   # full = every implemented class in the decoder | auto = only classes used
    "compiler": "auto",              # for .c input: auto | clang | gcc | a command name / path
    "cflags": ["-O1"],
    "shots": 1024,
    "aer": {"method": "matrix_product_state"},
    "ibm": {"channel": "ibm_quantum_platform", "token": "env:IBM_QUANTUM_TOKEN", "instance": None,
            "backend": "least_busy", "optimization_level": 1},
}


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULTS))
    if path and os.path.exists(path):
        user = json.load(open(path))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


GCC_NAMES = ["aarch64-linux-gnu-gcc", "aarch64-none-linux-gnu-gcc", "aarch64-none-elf-gcc", "aarch64-elf-gcc"]


def find_compiler(choice):
    """Return the command prefix that compiles C to an AArch64 object file."""
    if choice in ("auto", "clang") and shutil.which("clang"):
        return ["clang", "--target=aarch64-linux-gnu"]
    if choice in ("auto", "gcc"):
        for name in GCC_NAMES:
            if shutil.which(name):
                return [name]
        if choice == "gcc":
            sys.exit("error: no AArch64 gcc found (tried " + ", ".join(GCC_NAMES) + "); see README")
    if choice not in ("auto", "clang", "gcc") and shutil.which(choice):
        return [choice] + (["--target=aarch64-linux-gnu"] if "clang" in os.path.basename(choice) else [])
    sys.exit(f"error: compiler '{choice}' not found; install clang or an AArch64 gcc (see README)")


def compile_c(src, choice, cflags):
    cc = find_compiler(choice)
    out = os.path.join(tempfile.mkdtemp(prefix="arm_qpu_"), os.path.splitext(os.path.basename(src))[0] + ".o")
    cmd = cc + list(cflags) + ["-ffreestanding", "-c", src, "-o", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.exit("compile failed: " + " ".join(cmd) + "\n" + p.stderr)
    print("compiled: " + " ".join(cmd))
    return out, " ".join(cmd)


def sx(v, W):
    v &= (1 << W) - 1
    return v - (1 << W) if v >> (W - 1) else v


def parse_val(s):
    s = str(s).strip()
    if s.startswith("&"):
        return ("ptr", int(s[1:], 0))
    return ("int", int(s, 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("binary", help="C source (.c), AArch64 ELF/Mach-O object or executable, or raw .bin")
    ap.add_argument("--cc", help="compiler for .c input: clang | gcc | command (overrides config)")
    ap.add_argument("-O", dest="opt", help="optimization level for .c input, e.g. -O2 (overrides config cflags)")
    ap.add_argument("--entry", help="function to run (default: main, else the first function)")
    ap.add_argument("--args", nargs="*", default=[], help="X0, X1, ... initial values; '&k' = pointer to data cell k")
    ap.add_argument("--mem", default="", help="initial data memory cells (32-bit ints), comma separated")
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
    ap.add_argument("--report", help="report path prefix (default: <binary>.<entry>.report)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    compiled_with = None
    source = a.binary
    if a.binary.endswith(".c"):
        cflags = [f for f in cfg["cflags"] if not f.startswith("-O")] + [f"-O{a.opt}"] if a.opt else cfg["cflags"]
        obj, compiled_with = compile_c(a.binary, a.cc or cfg["compiler"], cflags)
        a.report = a.report or f"{os.path.splitext(a.binary)[0]}.{a.entry or 'main'}.report"
        a.binary = obj

    prog = load_program(a.binary, a.entry)
    code = prog["words"]
    n = len(code)
    slots = 2
    while slots < n + 1:
        slots *= 2
    # code addresses (4 * slot) and stack/data pointers must be non-negative W-bit values
    need = (4 * slots - 1).bit_length() + 1
    W = max(8, need) if cfg["register_width"] == "auto" else int(cfg["register_width"])
    if W < need:
        sys.exit(f"error: {n} instructions need {slots} program slots; code addresses need W >= {need} "
                 f"(register_width is {W})")
    if W > 16:
        sys.exit(f"error: program too large ({n} instructions) for the W <= 16 machine")
    words = layout(code, slots)
    asm = disassemble(b"".join(w.to_bytes(4, "little") for w in code), CODE_BASE)
    checks = [check(w, i, slots) for i, w in enumerate(code)]
    names_at = {v: k for k, v in prog["functions"].items()}

    # inputs
    raw_args = [parse_val(x) for x in a.args]
    mem_init = [int(x, 0) for x in a.mem.split(",") if x.strip()] if a.mem else []
    uses_mem = any(c.ok and c.cls in MEMOPS for c in checks) or any(t == "ptr" for t, _ in raw_args) or mem_init
    MEM = cfg["memory_words"]
    if MEM == "auto":
        MEM = (1 << (W - 4)) if uses_mem else 0
        while MEM and MEM < len(mem_init): MEM *= 2
    MEM = int(MEM)
    cpu_args = [DATA_BASE + 4 * v if t == "ptr" else v for t, v in raw_args]
    qpu_args = [4 * v if t == "ptr" else v for t, v in raw_args]

    # registers to instantiate
    used = set(range(len(raw_args))) | {0, 30}
    uses_sp = False
    for c in checks:
        if c.ok:
            used |= set(c.reads) | set(c.writes)
            uses_sp |= c.uses_sp
    uses_sp |= 31 in used
    used.discard(31)
    if cfg["registers"] == "all":
        regs = tuple(range(31))
    elif cfg["registers"] == "auto":
        regs = tuple(sorted(used))
    else:
        regs = tuple(sorted(set(cfg["registers"]) | {30}))
    classes = ALL_CLASSES if cfg["isa"] == "full" else tuple(sorted({c.cls for c in checks if c.ok} | {"hlt"}))

    # CPU reference
    ref = run_reference(words, W, prog["entry_index"], cpu_args, MEM, mem_init)
    executed = {}
    for i in ref["trace"]:
        executed[i] = executed.get(i, 0) + 1
    steps = ref["steps"] if cfg["max_steps"] == "auto" else int(cfg["max_steps"])

    report = dict(binary=a.binary, source=source, compiled_with=compiled_with, entry=prog["entry"], entry_index=prog["entry_index"], args=a.args,
                  memory_init=mem_init, config=cfg, unresolved_relocations=prog["unresolved"])
    report["code"] = [dict(index=i, address=f"0x{CODE_BASE + 4 * i:x}", word=f"{w:08x}", asm=asm[i],
                           function=names_at.get(i), cls=checks[i].cls, supported=checks[i].ok,
                           reason=checks[i].reason, executed=executed.get(i, 0)) for i, w in enumerate(code)]
    report["unsupported"] = [x for x in report["code"] if not x["supported"]]
    report["cpu"] = dict(steps=ref["steps"], halted=ref["halted"], error=ref["error"], issues=ref["issues"],
                         x0=ref["regs"][0])
    t0 = time.time()
    if ref["error"]:
        report["verdict"] = f"NOT RUN on QPU: the CPU run failed or reached an unsupported instruction ({ref['error']})"
        finish(report, a, prog, W)
        return

    m = QuantumARM(Config(W=W, regs=regs, sp=uses_sp, SLOTS=slots, STEPS=steps, MEM=MEM, classes=classes))
    gc = m.counts()
    report["machine"] = dict(W=W, registers=[f"x{k}" for k in regs] + (["sp"] if uses_sp else []), program_slots=slots,
                             steps=steps, data_memory_cells=MEM, decoder_classes=list(m.cfg.classes),
                             qubits=m.n, gates=gc, toffoli=gc.get("ccx", 0), build_seconds=round(time.time() - t0, 2))
    init = {i: v for i, v in enumerate(qpu_args)}
    init[30] = 4 * (slots - 1)
    if uses_sp:
        init[31] = 4 * MEM
    ones = m.load_bits(words, init, mem_init, pc=prog["entry_index"])

    backend = cfg["backend"]
    t1 = time.time()
    if backend == "simulator":
        st = simulate(m.g, m.n, ones)
        q = dict(regs={k: value(st, m.X[k]) for k in m.X}, flags=[st[x] for x in m.nzcv],
                 mem=[value(st, x) for x in m.ram], run=st[m.run[-1]], trap=any(st[x] for x in m.trap),
                 trace=[value(st, pcr) for pcr in m.pc_hist[:ref["steps"]]], probability=1.0)
        report["backend"] = dict(name="simulator", note="exact simulation of the reversible circuit on its basis-state input")
    else:
        q = run_sampled(m, ones, cfg, backend, report)
    report["backend"]["seconds"] = round(time.time() - t1, 2)
    if q is None:
        finish(report, a, prog, W)
        return

    mk = (1 << W) - 1
    rows = []
    for k in m.X:
        cpu = ref["regs"][k]
        rows.append(dict(reg="sp" if k == 31 else f"x{k}", cpu=cpu & mk, qpu=q["regs"][k],
                         cpu_signed=sx(cpu, W), qpu_signed=sx(q["regs"][k], W), match=(cpu & mk) == q["regs"][k]))
    mem_ok = [v & mk for v in ref["mem"]] == q["mem"]
    flags_ok = ref["flags"] == q["flags"]
    trace_ok = q.get("trace") is None or q["trace"] == ref["trace"]
    ok = all(r["match"] for r in rows) and mem_ok and flags_ok and trace_ok and q["run"] == 0 and not q["trap"]
    report["result"] = dict(registers=rows, flags=dict(cpu=ref["flags"], qpu=q["flags"]), memory_match=mem_ok,
                            memory=dict(cpu=[sx(v, W) for v in ref["mem"]], qpu=[sx(v, W) for v in q["mem"]]),
                            trace_match=trace_ok, halted=q["run"] == 0, trap=q["trap"], probability=q["probability"],
                            return_value=dict(cpu=sx(ref["regs"][0], W), qpu=sx(q["regs"][0], W)))
    exact = not ref["issues"]
    report["verdict"] = ("MATCH: the QPU produced the same result as the CPU" if ok else
                         "MISMATCH between QPU and CPU") + ("" if exact else
                         f" (warning: {len(ref['issues'])} value(s) did not fit the {W}-bit model, see model check)")
    finish(report, a, prog, W)


def run_sampled(m, ones, cfg, backend, report):
    groups = {f"x{k}" if k != 31 else "sp": m.X[k] for k in m.X}
    groups["nzcv"] = m.nzcv
    groups.update({f"ram{i}": r for i, r in enumerate(m.ram)})
    groups["run"] = [m.run[-1]]
    groups["trap"] = m.trap
    layout_bits = [(g, q) for g, qs in groups.items() for q in qs]
    from qiskit import QuantumCircuit, ClassicalRegister
    qc = m.to_qiskit(ones)
    cr = ClassicalRegister(len(layout_bits), "out")
    qc.add_register(cr)
    for i, (_, qb) in enumerate(layout_bits):
        qc.measure(qb, cr[i])
    shots = int(cfg["shots"])
    if backend == "aer":
        from qiskit_aer import AerSimulator
        from qiskit import transpile
        sim = AerSimulator(method=cfg["aer"].get("method", "automatic"))
        tqc = transpile(qc, basis_gates=["x", "cx", "ccx", "cswap", "measure"], optimization_level=0)
        counts = sim.run(tqc, shots=shots).result().get_counts()
        report["backend"] = dict(name=f"aer ({cfg['aer'].get('method')})", shots=shots)
    elif backend == "ibm":
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        from qiskit.transpiler import generate_preset_pass_manager
        ic = cfg["ibm"]
        token = ic.get("token")
        if token and token.startswith("env:"):
            token = os.environ.get(token[4:])
        kw = dict(channel=ic.get("channel"))
        if token: kw["token"] = token
        if ic.get("instance"): kw["instance"] = ic["instance"]
        service = QiskitRuntimeService(**kw)
        bk = service.least_busy(operational=True, simulator=False) if ic.get("backend") in (None, "least_busy") \
            else service.backend(ic["backend"])
        report["backend"] = dict(name=f"ibm:{bk.name}", shots=shots, device_qubits=bk.num_qubits)
        if m.n > bk.num_qubits:
            report["backend"]["note"] = (f"NOT SUBMITTED: the circuit needs {m.n} qubits, {bk.name} has {bk.num_qubits}. "
                                         "Use a smaller register_width / isa=auto / fewer registers, or wait for larger devices.")
            report["verdict"] = "NOT RUN on QPU hardware: circuit larger than the device"
            return None
        pm = generate_preset_pass_manager(backend=bk, optimization_level=int(ic.get("optimization_level", 1)))
        isa = pm.run(qc)
        ops = isa.count_ops()
        report["backend"]["transpiled"] = dict(depth=isa.depth(), two_qubit_gates=sum(v for k, v in ops.items() if k in ("cz", "ecr", "cx")))
        job = SamplerV2(mode=bk).run([isa], shots=shots)
        report["backend"]["job_id"] = job.job_id()
        counts = job.result()[0].data.out.get_counts()
    else:
        raise SystemExit(f"unknown backend '{backend}'")
    total = sum(counts.values())
    top = sorted(counts.items(), key=lambda kv: -kv[1])

    def decode(key):
        bits_ = key.replace(" ", "")[::-1]
        vals = {}
        for i, (g, _) in enumerate(layout_bits):
            vals.setdefault(g, []).append(int(bits_[i]))
        return vals
    best = decode(top[0][0])
    num = lambda bl: sum(b << i for i, b in enumerate(bl))
    report["backend"]["top_outcomes"] = [dict(probability=c / total, x0=sx(num(decode(k)["x0"]), m.cfg.W)) for k, c in top[:5]]
    return dict(regs={k: num(best["x%d" % k if k != 31 else "sp"]) for k in m.X}, flags=best["nzcv"],
                mem=[num(best[f"ram{i}"]) for i in range(len(m.ram))], run=best["run"][0], trap=any(best["trap"]),
                trace=None, probability=top[0][1] / total)


def finish(report, a, prog, W):
    prefix = a.report or f"{os.path.splitext(a.binary)[0]}.{prog['entry']}.report"
    json.dump(report, open(prefix + ".json", "w"), indent=2, default=str)
    open(prefix + ".md", "w").write(markdown(report, W))
    print(report["verdict"])
    r = report.get("result")
    if r:
        print(f"return value X0: CPU = {r['return_value']['cpu']}, QPU = {r['return_value']['qpu']}")
    mc = report.get("machine")
    if mc:
        print(f"quantum machine: {mc['qubits']} qubits, {sum(mc['gates'].values())} gates ({mc['toffoli']} Toffoli), "
              f"{mc['steps']} steps")
    if report["unsupported"]:
        print(f"{len(report['unsupported'])} unsupported instruction(s) in the loaded code (see report)")
    print(f"report: {prefix}.md")


def markdown(r, W):
    L = [f"# ARM on QPU: `{os.path.basename(r['binary'])}` :: `{r['entry']}`", "", f"**{r['verdict']}**", ""]
    res = r.get("result")
    if res:
        L += [f"Return value X0: CPU = **{res['return_value']['cpu']}**, QPU = **{res['return_value']['qpu']}**", ""]
    L += ["## Input", ""] + ([f"- source: `{r['source']}`, compiled with `{r['compiled_with']}`"] if r.get("compiled_with") else []) + [
          f"- binary: `{r['binary']}`, function `{r['entry']}` (instruction {r['entry_index']})",
          f"- arguments: {' '.join(r['args']) or '(none)'}; data memory init: {r['memory_init'] or '(none)'}",
          f"- backend: `{r['config']['backend']}`, register width W = {W}", ""]
    if r["unsupported"]:
        L += ["## Unsupported instructions", "",
              "These instructions are in the loaded code but not implemented by the quantum machine. "
              "A run that reaches one stops with a trap.", "",
              "| # | address | word | instruction | reason | executed by CPU |", "|---|---|---|---|---|---|"]
        for x in r["unsupported"]:
            L.append(f"| {x['index']} | {x['address']} | `{x['word']}` | `{x['asm']}` | {x['reason']} | {x['executed']} |")
        L.append("")
    if r.get("unresolved_relocations"):
        L += ["Unresolved relocations: " + "; ".join(r["unresolved_relocations"]), ""]
    if res:
        L += ["## Result: CPU vs QPU", "", "| register | CPU (low W bits, signed) | QPU | match |", "|---|---|---|---|"]
        for x in res["registers"]:
            L.append(f"| {x['reg']} | {x['cpu_signed']} | {x['qpu_signed']} | {'yes' if x['match'] else '**NO**'} |")
        L += ["", f"- NZCV flags: CPU {res['flags']['cpu']}, QPU {res['flags']['qpu']}",
              f"- data memory equal: {res['memory_match']}" + (f" (QPU: {res['memory']['qpu']})" if res['memory']['qpu'] else ""),
              f"- control-flow trace (PC per step) equal: {res['trace_match']}",
              f"- halted: {res['halted']}, trap: {res['trap']}, probability of this outcome: {res['probability']:.3f}", ""]
    mc = r.get("machine")
    if mc:
        L += ["## Quantum machine", "",
              f"- one fixed interpreter circuit: {mc['qubits']} qubits, gates {mc['gates']} ({mc['toffoli']} Toffoli)",
              f"- {mc['steps']} machine steps, {mc['program_slots']} program-memory slots x 32 qubits, "
              f"{mc['data_memory_cells']} data cells, registers {', '.join(mc['registers'])}",
              f"- decoder implements {len(mc['decoder_classes'])} instruction classes: {', '.join(mc['decoder_classes'])}", ""]
    bk = r.get("backend")
    if bk:
        L += ["## Backend", "", "```", json.dumps(bk, indent=2, default=str), "```", ""]
    cpu = r["cpu"]
    L += ["## Model check (CPU reference)", "",
          f"CPU reference: {cpu['steps']} steps, halted: {cpu['halted']}" + (f", error: {cpu['error']}" if cpu['error'] else ""), ""]
    if cpu["issues"]:
        L += [f"Values that do not fit the {W}-bit sign-extended model (the QPU result may differ):", ""]
        L += [f"- {x}" for x in cpu["issues"][:30]]
    else:
        L += [f"Every value of the run fits the {W}-bit model, so the QPU computes the exact low {W} bits of the AArch64 result."]
    L += ["", "## Code", "", "| # | address | word | instruction | class | supported | executed |", "|---|---|---|---|---|---|---|"]
    for x in r["code"]:
        fn = f"**{x['function']}:** " if x["function"] else ""
        L.append(f"| {x['index']} | {x['address']} | `{x['word']}` | {fn}`{x['asm']}` | {x['cls'] or '-'} | "
                 f"{'yes' if x['supported'] else 'no: ' + x['reason']} | {x['executed']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
