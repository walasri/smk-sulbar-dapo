#!/usr/bin/env python3
"""
Dashboard Web Interaktif Data SMK Sulawesi Barat
Jalankan: python3 generate_web.py
Lalu buka: http://localhost:8000
"""

import os
import json
import subprocess
import sys
import threading
import time
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
CSV_LENGKAP = DATA_DIR / "smk_sulbar_lengkap.csv"
CSV_JURUSAN = DATA_DIR / "smk_sulbar_jurusan.csv"
CSV_MOU     = DATA_DIR / "smk_sulbar_mou.csv"
HTML_TEMPLATE = Path("templates/index.html")
SCRAPER = Path(__file__).parent / "scrape_sulbar.py"
PORT = 8000

# ─────────────────────────────────────────────
# Global state untuk scrape
# ─────────────────────────────────────────────
scrape_lock = threading.Lock()
scrape_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "mode": None,        # "ringan" atau "lengkap"
    "progress": "",      # baris terakhir stdout scraper
    "done": False,
    "success": False,
    "error": "",
}


def load_data():
    """(Re)load semua CSV ke global df / df_jurusan / df_mou + rebuild meta."""
    global df, df_jurusan, df_mou, meta_json

    print("⏳ Memuat data SMK Sulawesi Barat...")
    df = pd.read_csv(CSV_LENGKAP, dtype=str).fillna("")

    df_jurusan = None
    if CSV_JURUSAN.exists():
        df_jurusan = pd.read_csv(CSV_JURUSAN, dtype=str).fillna("")

    df_mou = None
    if CSV_MOU.exists():
        df_mou = pd.read_csv(CSV_MOU, dtype=str).fillna("")

    kabupaten_list = sorted(df["kab_kota"].unique().tolist())

    jurusan_set = set()
    src = df_jurusan if df_jurusan is not None else df
    if "jurusan" in src.columns:
        for val in src["jurusan"].dropna():
            for j in val.split(" | "):
                j = j.strip()
                if j:
                    jurusan_set.add(j)

    meta = {
        "total_sekolah": len(df),
        "kabupaten_list": kabupaten_list,
        "jurusan_list": sorted(jurusan_set),
        "last_refresh": scrape_state.get("finished_at", ""),
    }
    meta_json = json.dumps(meta, ensure_ascii=False)
    print(f"✓ {len(df)} SMK dimuat | {len(kabupaten_list)} kabupaten | {len(meta['jurusan_list'])} jurusan")


def _run_scraper(detail: bool):
    """Jalankan scrape_sulbar.py di background thread."""
    global scrape_state
    mode = "lengkap" if detail else "ringan"
    cmd = [sys.executable, str(SCRAPER)]
    if detail:
        cmd.append("--detail")

    with scrape_lock:
        scrape_state.update({
            "running": True,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "mode": mode,
            "progress": "Memulai scraping...",
            "done": False,
            "success": False,
            "error": "",
        })

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(Path(__file__).parent),
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                with scrape_lock:
                    scrape_state["progress"] = line[:200]

        proc.wait()
        ok = proc.returncode == 0

        with scrape_lock:
            scrape_state["running"] = False
            scrape_state["done"] = True
            scrape_state["success"] = ok
            scrape_state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if not ok:
                scrape_state["error"] = f"Exit code {proc.returncode}"

        if ok:
            print("🔄 Scraper selesai — reload data...")
            load_data()
            print("✓ Data berhasil di-reload!")

    except Exception as e:
        with scrape_lock:
            scrape_state["running"] = False
            scrape_state["done"] = True
            scrape_state["success"] = False
            scrape_state["error"] = str(e)
            scrape_state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────
# Validasi + load awal
# ─────────────────────────────────────────────
if not CSV_LENGKAP.exists():
    print(f"❌ File {CSV_LENGKAP} tidak ditemukan.")
    print("Jalankan scrape_sulbar.py terlebih dahulu.")
    exit(1)

df = df_jurusan = df_mou = meta_json = None
load_data()


# ─────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────
class APIServer(http.server.BaseHTTPRequestHandler):

    # ---- routing ----
    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path

        if p == "/api/meta":
            return self._json(meta_json)

        if p == "/api/sekolah":
            return self._api_sekolah(parsed)

        if p == "/api/detail":
            return self._api_detail(parsed)

        if p == "/api/statistik":
            return self._api_statistik()

        if p == "/api/refresh/status":
            with scrape_lock:
                return self._json(json.dumps(scrape_state, ensure_ascii=False))

        if p in ("/", "/index.html"):
            return self._serve_html()

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            return self._api_refresh(parsed)
        self.send_error(404)

    # ---- handlers ----
    def _api_sekolah(self, parsed):
        qs = parse_qs(parsed.query)
        kab         = qs.get("kab_kota", [""])[0]
        status      = qs.get("status", [""])[0]
        akreditasi  = qs.get("akreditasi", [""])[0]
        jur_filter  = qs.get("jurusan", [""])[0]
        q           = qs.get("q", [""])[0].lower()

        src = df_jurusan if df_jurusan is not None else df
        filtered = src.copy()

        if kab:
            filtered = filtered[filtered["kab_kota"] == kab]
        if status:
            filtered = filtered[filtered["status"] == status]
        if akreditasi:
            filtered = filtered[filtered["akreditasi"] == akreditasi]
        if jur_filter and "jurusan" in filtered.columns:
            filtered = filtered[filtered["jurusan"].str.contains(jur_filter, case=False, na=False)]
        if q:
            filtered = filtered[filtered["nama"].str.lower().str.contains(q, na=False)]

        for col in ("jml_siswa", "total_rombel", "jml_jurusan"):
            if col in filtered.columns:
                filtered[col] = pd.to_numeric(filtered[col], errors="coerce").fillna(0).astype(int)

        self._json(json.dumps({"count": len(filtered), "data": filtered.to_dict("records")}, ensure_ascii=False))

    def _api_detail(self, parsed):
        npsn = parse_qs(parsed.query).get("npsn", [""])[0]
        result = {}
        row = df[df["npsn"] == npsn]
        if not row.empty:
            result["sekolah"] = row.iloc[0].to_dict()
        if df_jurusan is not None:
            jrow = df_jurusan[df_jurusan["npsn"] == npsn]
            if not jrow.empty:
                raw = jrow.iloc[0].get("jurusan", "")
                result["jurusan"] = [j.strip() for j in raw.split(" | ") if j.strip()]
        if df_mou is not None:
            result["mou"] = df_mou[df_mou["npsn"] == npsn].to_dict("records")
        self._json(json.dumps(result, ensure_ascii=False))

    def _api_statistik(self):
        stats = {
            "total_smk":    len(df),
            "total_siswa":  int(pd.to_numeric(df.get("jml_siswa", pd.Series()), errors="coerce").fillna(0).sum()),
            "total_rombel": int(pd.to_numeric(df.get("total_rombel", pd.Series()), errors="coerce").fillna(0).sum()),
            "total_mou":    len(df_mou) if df_mou is not None else 0,
            "per_kabupaten":  df.groupby("kab_kota").size().to_dict(),
            "per_status":     df.groupby("status").size().to_dict() if "status" in df.columns else {},
            "per_akreditasi": df.groupby("akreditasi").size().to_dict() if "akreditasi" in df.columns else {},
        }
        self._json(json.dumps(stats, ensure_ascii=False))

    def _api_refresh(self, parsed):
        qs = parse_qs(parsed.query)
        mode = qs.get("mode", ["ringan"])[0]
        detail = mode == "lengkap"

        with scrape_lock:
            if scrape_state["running"]:
                self._json(json.dumps({"ok": False, "error": "Scrape sedang berjalan"}, ensure_ascii=False))
                return

        t = threading.Thread(target=_run_scraper, args=(detail,), daemon=True)
        t.start()
        self._json(json.dumps({"ok": True, "mode": mode}, ensure_ascii=False))

    def _serve_html(self):
        if HTML_TEMPLATE.exists():
            content = HTML_TEMPLATE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "index.html tidak ditemukan di templates/")

    def _json(self, data: str):
        encoded = data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


os.makedirs("templates", exist_ok=True)
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("", PORT), APIServer) as httpd:
    print(f"\n🌐 Server berjalan di: http://localhost:{PORT}")
    print("   Tekan Ctrl+C untuk stop\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server dihentikan")
