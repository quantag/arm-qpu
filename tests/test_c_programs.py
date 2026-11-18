"""End-to-end: C programs compiled by clang (-O0/-O1/-O2) for AArch64, run by arm_qpu.py on the
quantum interpreter (exact simulator backend) and on the CPU reference; every case must MATCH.
Run: python3 -m tests.test_c_programs [clang|gcc]"""
import json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = [
    ("factor.c", "smallest_factor", ["91"], ""),
    ("factor.c", "factorize", ["84", "&0"], ""),
    ("factor.c", "factorize", ["97", "&0"], ""),
    ("algorithms.c", "gcd", ["84", "36"], ""),
    ("algorithms.c", "fib", ["10"], ""),
    ("algorithms.c", "is_prime", ["89"], ""),
    ("algorithms.c", "is_prime", ["91"], ""),
    ("algorithms.c", "popcount", ["109"], ""),
    ("algorithms.c", "collatz_steps", ["6"], ""),
    ("algorithms.c", "isqrt", ["70"], ""),
    ("algorithms.c", "power_mod", ["3", "5", "13"], ""),
    ("algorithms.c", "max3", ["-7", "12", "5"], ""),
    ("algorithms.c", "sum_of_squares", ["5", "-6"], ""),
    ("algorithms.c", "bubble_sort", ["&0", "6"], "9,-3,7,1,0,4"),
    ("algorithms.c", "binary_search", ["&0", "7", "11"], "-5,0,3,8,11,20,31"),
    ("algorithms.c", "digit_sum", ["97"], ""),
]
# Known model limit: compilers turn n / 10 into a multiply by 0xCCCCCCCD and a 35-bit shift (clang from -O1,
# gcc already at -O0). Those values do not fit W <= 16 bits; the reference must flag it (no match required).
EXPECT_MODEL_LIMIT = {"clang": {("digit_sum", "O1"), ("digit_sum", "O2")},
                      "gcc": {("digit_sum", "O0"), ("digit_sum", "O1"), ("digit_sum", "O2")}}

COMPILERS = {"clang": ["clang", "--target=aarch64-linux-gnu"], "gcc": ["aarch64-linux-gnu-gcc"]}

if __name__ == "__main__":
    cc_name = sys.argv[1] if len(sys.argv) > 1 else "clang"
    cc, limits = COMPILERS[cc_name], EXPECT_MODEL_LIMIT[cc_name]
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        for src in sorted({c[0] for c in CASES}):
            for o in ("O0", "O1", "O2"):
                subprocess.run(cc + [f"-{o}", "-c", os.path.join(ROOT, "examples", src),
                                "-o", os.path.join(d, f"{src}.{o}.o")], check=True)
        for src, fn, args, mem in CASES:
            for o in ("O0", "O1", "O2"):
                obj = os.path.join(d, f"{src}.{o}.o")
                cmd = [sys.executable, os.path.join(ROOT, "arm_qpu.py"), obj, "--entry", fn, "--args", *args,
                       "--report", os.path.join(d, "r")] + ([f"--mem={mem}"] if mem else [])
                p = subprocess.run(cmd, capture_output=True, text=True)
                rep = json.load(open(os.path.join(d, "r.json"))) if os.path.exists(os.path.join(d, "r.json")) else {}
                ok = rep.get("verdict", "").startswith("MATCH")
                if (fn, o) in limits:
                    ok = bool(rep.get("cpu", {}).get("issues"))     # must be detected and reported
                fails += not ok
                res = rep.get("result", {})
                mc = rep.get("machine", {})
                print(f"{'PASS' if ok else 'FAIL'}{' (model limit reported)' if (fn, o) in limits else ''} {fn}({', '.join(args)}) -{o}: QPU={res.get('return_value', {}).get('qpu')} "
                      f"CPU={res.get('return_value', {}).get('cpu')} steps={mc.get('steps')} qubits={mc.get('qubits')}"
                      + ("" if ok else f"\n     {rep.get('verdict') or p.stderr[-500:]}"))
                os.path.exists(os.path.join(d, "r.json")) and os.remove(os.path.join(d, "r.json"))
    print("all passed" if not fails else f"{fails} failed")
    sys.exit(1 if fails else 0)
