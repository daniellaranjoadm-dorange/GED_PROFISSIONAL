import os
import sys
from pathlib import Path

ROOT_MARKER = "manage.py"


def find_root(start: Path) -> Path:
    cur = start.resolve()
    while True:
        if (cur / ROOT_MARKER).exists():
            return cur
        if cur.parent == cur:
            raise RuntimeError(f"{ROOT_MARKER} not found from {start}")
        cur = cur.parent


ROOT = find_root(Path(__file__).parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import platform
import re
import time
import zipfile
from datetime import datetime
from typing import Dict, List, Tuple

MOJIBAKE_TOKENS = ["Ãƒ", "Ã‚", "ï¿½"]
GLOBAL_SELECTOR_RE = re.compile(r"^\s*(body|html|main|table|h1|h2)\b", re.IGNORECASE)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run_cmd(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    import subprocess

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            shell=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except Exception as exc:
        return 1, f"COMMAND_FAIL: {cmd}\n{exc}\n"


def list_templates(root: Path) -> List[Path]:
    exclude = {"_backup", "backup", "old", "Historico", "migrations", "venv", ".venv"}
    out = []
    for path in root.rglob("*.html"):
        parts = {p for p in path.parts}
        if "templates" not in parts:
            continue
        if parts.intersection(exclude):
            continue
        out.append(path)
    return out


def extract_class_names(text: str) -> List[str]:
    classes = []
    for m in re.finditer(r'class="([^"]+)"', text):
        classes.extend([c for c in m.group(1).split() if c.strip()])
    return classes


def scan_templates(templates: List[Path]) -> Dict[str, List[str]]:
    findings = {
        "mojibake": [],
        "inline_style": [],
        "global_selectors": [],
    }
    for tpl in templates:
        try:
            lines = tpl.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            if any(tok in line for tok in MOJIBAKE_TOKENS):
                findings["mojibake"].append(f"{tpl}:{idx}:{line}")
            if "<style" in line:
                findings["inline_style"].append(f"{tpl}:{idx}:{line}")
            if GLOBAL_SELECTOR_RE.search(line) and ".doc-wrapper" not in line:
                findings["global_selectors"].append(f"{tpl}:{idx}:{line}")
    return findings


def scan_static(root: Path) -> List[str]:
    out = []
    static_root = root / "static"
    if not static_root.exists():
        return out
    for path in static_root.rglob("*"):
        if path.suffix.lower() not in {".css", ".js"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            if re.match(r"^\s*(body|html|main)\b", line):
                out.append(f"{path}:{idx}:GLOBAL_SELECTOR:{line}")
            if re.search(r"(?i)overflow\s*:\s*hidden", line):
                out.append(f"{path}:{idx}:OVERFLOW_HIDDEN:{line}")
    return out


def medicao_diagnose(root: Path) -> Dict[str, str]:
    result = {
        "template_path": "not_found",
        "thead_cols": "0",
        "tfoot_cols": "0",
        "tfoot_colspan": "no",
        "line_artifacts": "none_detected",
        "totals_logic": "not_checked",
    }
    tpl = root / "apps/documentos/templates/documentos/medicao.html"
    if tpl.exists():
        result["template_path"] = str(tpl)
        text = tpl.read_text(encoding="utf-8")
        thead = re.search(r"<thead>(.*?)</thead>", text, re.S)
        tfoot = re.search(r"<tfoot>(.*?)</tfoot>", text, re.S)
        if thead:
            result["thead_cols"] = str(thead.group(1).count("<th"))
        if tfoot:
            result["tfoot_cols"] = str(
                tfoot.group(1).count("<td") + tfoot.group(1).count("<th")
            )
            result["tfoot_colspan"] = "yes" if "colspan" in tfoot.group(1) else "no"
        if re.search(r"<hr|divider|separator|footer-line", text, re.I):
            result["line_artifacts"] = "possible_hr_or_divider"
        elif re.search(r"border-bottom\s*:\s*1px", text, re.I):
            result["line_artifacts"] = "possible_border_bottom"

    view = root / "apps/documentos/views.py"
    if view.exists():
        vtxt = view.read_text(encoding="utf-8")
        if "totais_gerais" in vtxt and "total_geral" in vtxt:
            result["totals_logic"] = "totais_gerais present; total_geral set"
        else:
            result["totals_logic"] = "totals not found in view"
    return result


def diagnose_environment() -> Dict[str, str]:
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "timezone": time.tzname[0] if time.tzname else "unknown",
    }
    return env


def diagnose_django_settings(python: str, root: Path) -> Dict[str, str]:
    info = {
        "django": "unknown",
        "debug": "unknown",
        "allowed_hosts": "unknown",
        "db_engine": "unknown",
        "storages_default": "unknown",
        "time_zone": "unknown",
        "settings_module": "ged.settings",
    }
    code, out = run_cmd([python, "manage.py", "--version"], root)
    if code == 0:
        info["django"] = out.strip()
    else:
        code, out = run_cmd([python, "-c", "import django; print(django.get_version())"], root)
        if code == 0:
            info["django"] = out.strip()

    settings_code = (
        "import json; from django.conf import settings;"
        "print(json.dumps({"
        "'DEBUG': getattr(settings,'DEBUG',None),"
        "'ALLOWED_HOSTS': getattr(settings,'ALLOWED_HOSTS',[]),"
        "'DB_ENGINE': getattr(settings,'DATABASES',{}).get('default',{}).get('ENGINE',''),"
        "'STORAGES_DEFAULT': getattr(settings,'STORAGES',{}).get('default',{}).get('BACKEND',''),"
        "'TIME_ZONE': getattr(settings,'TIME_ZONE','')"
        "}))"
    )
    code, out = run_cmd([python, "manage.py", "shell", "-c", settings_code], root)
    if code == 0:
        try:
            payload = json.loads(out.strip().splitlines()[-1])
            info["debug"] = str(payload.get("DEBUG"))
            info["allowed_hosts"] = ",".join(payload.get("ALLOWED_HOSTS", []))
            info["db_engine"] = payload.get("DB_ENGINE") or "unknown"
            info["storages_default"] = payload.get("STORAGES_DEFAULT") or "unknown"
            info["time_zone"] = payload.get("TIME_ZONE") or "unknown"
        except Exception:
            pass
    return info


def write_report(path: Path, summary: Dict[str, str], sections: Dict[str, str]) -> None:
    lines = []
    lines.append("# GED_DIAGNOSTICO")
    lines.append("")
    lines.append("## Sumario")
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    for title, body in sections.items():
        lines.append(f"## {title}")
        lines.append(body)
        lines.append("")
    write_text(path, "\n".join(lines))


def main() -> int:
    root = ROOT
    python = sys.executable
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = root / "tools" / "output" / timestamp
    logs_dir = out_root / "logs"
    snap_dir = out_root / "snapshots"
    ensure_dir(logs_dir)
    ensure_dir(snap_dir)

    env_info = diagnose_environment()
    django_info = diagnose_django_settings(python, root)

    code, out = run_cmd(
        [
            python,
            "-m",
            "compileall",
            "apps",
            "ged",
            "manage.py",
            "-x",
            r"[/\\](?:_backup|_Backup|scripts)[/\\]",
        ],
        root,
    )
    write_text(logs_dir / "compileall.txt", out)

    code_check, out_check = run_cmd([python, "manage.py", "check"], root)
    write_text(logs_dir / "django_check.txt", out_check)

    code_mig, out_mig = run_cmd(
        [python, "manage.py", "makemigrations", "--check", "--dry-run"], root
    )
    write_text(logs_dir / "makemigrations_check.txt", out_mig)

    code_show, out_show = run_cmd([python, "manage.py", "showmigrations", "--plan"], root)
    write_text(logs_dir / "showmigrations_plan.txt", out_show)

    url_script = logs_dir / "url_reverse_smoke.py"
    url_script.write_text(
        "\n".join(
            [
                "from django.urls import reverse",
                "names = [",
                "    'documentos:listar_documentos',",
                "    'documentos:upload_documento',",
                "    'documentos:importar_ldp',",
                "    'documentos:painel_workflow',",
                "    'documentos:medicao',",
                "    'documentos:lixeira',",
                "    'contas:minhas_configuracoes',",
                "    'contas:usuarios_permissoes',",
                "    'solicitacoes:listar_solicitacoes',",
                "]",
                "failed = False",
                "for name in names:",
                "    try:",
                "        print(f'OK {name} -> {reverse(name)}')",
                "    except Exception as exc:",
                "        failed = True",
                "        print(f'FAIL {name} -> {exc}')",
                "raise SystemExit(2 if failed else 0)",
            ]
        ),
        encoding="utf-8",
    )
    url_exit, url_out = run_cmd(
        [python, "manage.py", "shell", "-c", f"exec(open(r'{url_script}').read())"],
        root,
    )
    reverse_fail = url_exit != 0
    write_text(logs_dir / "url_reverse_smoke.txt", url_out)

    templates = list_templates(root)
    tpl_findings = scan_templates(templates)
    write_text(snap_dir / "templates_mojibake.txt", "\n".join(tpl_findings["mojibake"]))
    write_text(
        snap_dir / "templates_inline_style.txt", "\n".join(tpl_findings["inline_style"])
    )
    write_text(
        snap_dir / "templates_global_selectors.txt",
        "\n".join(tpl_findings["global_selectors"]),
    )

    static_findings = scan_static(root)
    write_text(snap_dir / "static_scan.txt", "\n".join(static_findings))

    base_classes = set()
    base_tpl = root / "apps/documentos/templates/documentos/base.html"
    if base_tpl.exists():
        base_classes.update(extract_class_names(base_tpl.read_text(encoding="utf-8")))
    class_counts: Dict[str, int] = {}
    for tpl in templates:
        classes = extract_class_names(tpl.read_text(encoding="utf-8"))
        for c in classes:
            class_counts[c] = class_counts.get(c, 0) + 1
    common = sorted(class_counts.items(), key=lambda kv: kv[1], reverse=True)[:40]
    overlap = sorted([c for c in class_counts.keys() if c in base_classes])
    write_text(
        snap_dir / "class_conflicts.txt",
        "COMMON_CLASSES:\n"
        + "\n".join([f"{k}: {v}" for k, v in common])
        + "\n\nBASE_OVERLAP:\n"
        + "\n".join(overlap),
    )

    medicao_info = medicao_diagnose(root)
    write_text(snap_dir / "medicao_diagnostico.txt", json.dumps(medicao_info, indent=2))

    summary = {
        "python": env_info["python"],
        "django": django_info["django"],
        "compileall": "ok" if code == 0 else "fail",
        "django_check": "ok" if code_check == 0 else "fail",
        "migrations": "ok" if code_mig == 0 else "pending_or_fail",
        "url_reverse": "ok" if not reverse_fail else "fail",
        "templates_mojibake": "found" if tpl_findings["mojibake"] else "none",
    }

    sections = {
        "Ambiente": "\n".join([f"- {k}: {v}" for k, v in env_info.items()]),
        "Settings (public)": "\n".join([f"- {k}: {v}" for k, v in django_info.items()]),
        "Templates": (
            f"- mojibake: {len(tpl_findings['mojibake'])}\n"
            f"- inline_style: {len(tpl_findings['inline_style'])}\n"
            f"- global_selectors: {len(tpl_findings['global_selectors'])}"
        ),
        "Static": f"- findings: {len(static_findings)}",
        "Medicao": json.dumps(medicao_info, indent=2),
    }

    write_report(out_root / "GED_DIAGNOSTICO.md", summary, sections)

    zip_path = root / "GED_DIAGNOSTICO.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_root / "GED_DIAGNOSTICO.md", "GED_DIAGNOSTICO.md")
        for p in logs_dir.rglob("*.txt"):
            zf.write(p, f"logs/{p.name}")
        for p in snap_dir.rglob("*.txt"):
            zf.write(p, f"snapshots/{p.name}")

    print("GERADO: GED_DIAGNOSTICO.zip")

    exit_code = 0
    if tpl_findings["mojibake"] or reverse_fail or code_mig != 0:
        exit_code = 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
