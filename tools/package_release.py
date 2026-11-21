"""Đóng gói bản phát hành chạy được cho Quán Ăn Chợ Nổi (`quan-an-cho-noi-v{version}.zip` & `.tar.gz`)."""

import argparse
import os
import sys
import tarfile
import time
import zipfile

ROOT_FILES = ("game.contract.json", "README.md", "CHANGELOG.md", "CREDITS.md", "LICENSE")
RUN_SH = "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")\"\nexec python3 -m chonoi.live --mode day \"$@\"\n"
RUN_BAT = "@echo off\r\ncd /d \"%~dp0\"\r\npython -m chonoi.live --mode day %*\r\n"


def _iter_repo_files(repo_root: str):
    pkg_dir = os.path.join(repo_root, "chonoi")
    for cur_root, dirs, files in os.walk(pkg_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and not d.startswith("."))
        for fname in sorted(files):
            if fname.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(cur_root, fname)
            rel = os.path.relpath(full, repo_root).replace("\\", "/")
            yield full, rel
    for name in ROOT_FILES:
        full = os.path.join(repo_root, name)
        if os.path.isfile(full):
            yield full, name


def build_bundles(repo_root: str, out_dir: str, version: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    stem = f"quan-an-cho-noi-v{version}"
    zip_path = os.path.join(out_dir, f"{stem}.zip")
    tgz_path = os.path.join(out_dir, f"{stem}.tar.gz")
    entries = list(_iter_repo_files(repo_root))
    fixed_ts = int(time.time())

    # ZIP bundle
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full, rel in entries:
            arc = f"{stem}/{rel}"
            zf.write(full, arc)
        z_sh = zipfile.ZipInfo(f"{stem}/run.sh", date_time=time.localtime(fixed_ts)[:6])
        z_sh.external_attr = (0o100755 & 0xFFFF) << 16
        zf.writestr(z_sh, RUN_SH.encode("utf-8"))
        z_bat = zipfile.ZipInfo(f"{stem}/run.bat", date_time=time.localtime(fixed_ts)[:6])
        z_bat.external_attr = (0o100644 & 0xFFFF) << 16
        zf.writestr(z_bat, RUN_BAT.encode("utf-8"))

    # TAR.GZ bundle (Unix/macOS friendly, normalized permissions & LF run.sh)
    with tarfile.open(tgz_path, "w:gz") as tf:
        for full, rel in entries:
            arc = f"{stem}/{rel}"
            data = open(full, "rb").read()
            if rel.endswith((".py", ".html", ".json", ".md")) or rel == "LICENSE":
                data = data.replace(b"\r\n", b"\n")
            ti = tarfile.TarInfo(arc)
            ti.size = len(data)
            ti.mode = 0o644
            ti.mtime = fixed_ts
            tf.addfile(ti, __import__("io").BytesIO(data))

        sh_bytes = RUN_SH.encode("utf-8")
        ti_sh = tarfile.TarInfo(f"{stem}/run.sh")
        ti_sh.size = len(sh_bytes)
        ti_sh.mode = 0o755
        ti_sh.mtime = fixed_ts
        tf.addfile(ti_sh, __import__("io").BytesIO(sh_bytes))

        bat_bytes = RUN_BAT.encode("utf-8")
        ti_bat = tarfile.TarInfo(f"{stem}/run.bat")
        ti_bat.size = len(bat_bytes)
        ti_bat.mode = 0o644
        ti_bat.mtime = fixed_ts
        tf.addfile(ti_bat, __import__("io").BytesIO(bat_bytes))

    return {"zip": zip_path, "tar_gz": tgz_path}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="package_release")
    p.add_argument("--out-dir", default="dist")
    p.add_argument("--version", default="1.0.0")
    a = p.parse_args(argv)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = a.out_dir if os.path.isabs(a.out_dir) else os.path.join(repo_root, a.out_dir)
    res = build_bundles(repo_root, out, a.version)
    print(f"Created {res['zip']}")
    print(f"Created {res['tar_gz']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
