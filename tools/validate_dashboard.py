from pathlib import Path
from html.parser import HTMLParser

p = Path(r"D:\GED_PROFISSIONAL\outputs\DASHBOARD_GESTAO_INTEGRADA_DOC_CONTROL_R13.html")
t = p.read_text(encoding="utf-8")
HTMLParser().feed(t)
assert "<title>" in t and "<h1>" in t
assert t.count('<article class="card') == 12
assert t.count("<table>") == 2

agreed_hm, dc_hm, at_hm = 1028.5, 429.5, 684.0
agreed_cost, dc_cost, at_cost = 7290570.241, 3670683.617, 3620591.24
combined_cost = dc_cost + at_cost
target = agreed_cost * 0.8
gap = combined_cost - target
assert dc_hm + at_hm == 1113.5
assert round(combined_cost) == 7291275
assert round(gap) == 1458819
print({"cards": 12, "tables": 2, "combined_hm": dc_hm + at_hm,
       "combined_cost": combined_cost, "target_80pct": target,
       "gap": gap, "bytes": p.stat().st_size})
