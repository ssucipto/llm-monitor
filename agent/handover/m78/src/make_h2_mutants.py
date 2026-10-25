"""Write files/h2-mutants.tsv: the five M78-H2 mutants, '~' form (the stripped decision line, any indentation)."""
import os
import sys

sys.path.insert(0, "D:/Project/Homelab/agent/delegation/tools")
import mutation_proof as mp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
F = "llm-monitor/usage_ledger.py"
D = {
    "D1": 'con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")',
    "D2": "if size < offset:  # rotated or rewritten: read again from 0 (the unique key prevents double counting)",
    "D3": 'end = data.rfind(b"\\n") + 1  # only complete lines; a line still being written waits for the next pass',
    "D4": 'return (p or "").replace("\\\\", "/").rstrip("/").lower()',
    "D5": 'orch = None if status.get("claude_code") != "ok" else orch',
}
M = [(D["D1"], "pass"), (D["D2"], "if False:"), (D["D3"], "end = len(data)"),
     (D["D4"], 'return (p or "").replace("\\\\", "/").rstrip("/")'), (D["D5"], "orch = orch")]
if __name__ == "__main__":
    out = os.path.join(HERE, "files", "h2-mutants.tsv")
    open(out, "w", encoding="utf8", newline="\n").write("".join(f"{F}\t~{mp.escape(a)}\t{mp.escape(b)}\n" for a, b in M))
    print("written", out, len(M))
