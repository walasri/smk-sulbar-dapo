#!/usr/bin/env python3
"""
Dashboard Web Interaktif Data SMK Sulawesi Barat
Jalankan: python3 generate_web.py
Lalu buka: http://localhost:8000
"""

import os
import json
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
CSV_LENGKAP = DATA_DIR / "smk_sulbar_lengkap.csv"
CSV_JURUSAN = DATA_DIR / "smk_sulbar_jurusan.csv"
CSV_MOU = DATA_DIR / "smk_sulbar_mou.csv"
HTML_TEMPLATE = Path("templates/index.html")
PORT = 8000

# Validasi file data
for f in [CSV_LENGKAP]:
    if not f.exists():
        print(f"❌ File {f} tidak ditemukan.")
        print("Jalankan scrape_sulbar.py terlebih dahulu.")
        exit(1)

print("⏳ Memuat data SMK Sulawesi Barat...")
df = pd.read_csv(CSV_LENGKAP, dtype=str).fillna("")

# Load jurusan jika ada
df_jurusan = None
if CSV_JURUSAN.exists():
    df_jurusan = pd.read_csv(CSV_JURUSAN, dtype=str).fillna("")

# Load MOU jika ada
df_mou = None
if CSV_MOU.exists():
    df_mou = pd.read_csv(CSV_MOU, dtype=str).fillna("")

# Precompute data untuk dropdown
print("🗺️  Membangun struktur data...")
kabupaten_list = sorted(df["kab_kota"].unique().tolist())

# Precompute jurusan unik
jurusan_set = set()
if df_jurusan is not None and "jurusan" in df_jurusan.columns:
    for val in df_jurusan["jurusan"].dropna():
        for j in val.split(" | "):
            j = j.strip()
            if j:
                jurusan_set.add(j)
elif "jurusan" in df.columns:
    for val in df["jurusan"].dropna():
        for j in val.split(" | "):
            j = j.strip()
            if j:
                jurusan_set.add(j)
jurusan_list = sorted(jurusan_set)

meta = {
    "total_sekolah": len(df),
    "kabupaten_list": kabupaten_list,
    "jurusan_list": jurusan_list,
}
meta_json = json.dumps(meta, ensure_ascii=False)
print(f"✓ {len(df)} SMK dimuat | {len(kabupaten_list)} kabupaten | {len(jurusan_list)} jurusan")


class APIServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        # API: metadata (dropdown data)
        if parsed.path == "/api/meta":
            self._json(meta_json)

        # API: daftar sekolah dengan filter
        elif parsed.path == "/api/sekolah":
            qs = parse_qs(parsed.query)
            kab = qs.get("kab_kota", [""])[0]
            status = qs.get("status", [""])[0]
            akreditasi = qs.get("akreditasi", [""])[0]
            jurusan_filter = qs.get("jurusan", [""])[0]
            q = qs.get("q", [""])[0].lower()

            src = df_jurusan if df_jurusan is not None else df
            filtered = src.copy()

            if kab:
                filtered = filtered[filtered["kab_kota"] == kab]
            if status:
                filtered = filtered[filtered["status"] == status]
            if akreditasi:
                filtered = filtered[filtered["akreditasi"] == akreditasi]
            if jurusan_filter and "jurusan" in filtered.columns:
                filtered = filtered[filtered["jurusan"].str.contains(jurusan_filter, case=False, na=False)]
            if q:
                filtered = filtered[filtered["nama"].str.lower().str.contains(q, na=False)]

            numeric_cols = ["jml_siswa", "total_rombel", "jml_jurusan"]
            for col in numeric_cols:
                if col in filtered.columns:
                    filtered[col] = pd.to_numeric(filtered[col], errors="coerce").fillna(0).astype(int)

            response = {
                "count": len(filtered),
                "data": filtered.to_dict("records")
            }
            self._json(json.dumps(response, ensure_ascii=False))

        # API: detail sekolah by NPSN
        elif parsed.path == "/api/detail":
            qs = parse_qs(parsed.query)
            npsn = qs.get("npsn", [""])[0]
            result = {}

            row = df[df["npsn"] == npsn]
            if not row.empty:
                result["sekolah"] = row.iloc[0].to_dict()

            if df_jurusan is not None:
                jrow = df_jurusan[df_jurusan["npsn"] == npsn]
                if not jrow.empty:
                    jurusan_raw = jrow.iloc[0].get("jurusan", "")
                    result["jurusan"] = [j.strip() for j in jurusan_raw.split(" | ") if j.strip()]

            if df_mou is not None:
                mou_rows = df_mou[df_mou["npsn"] == npsn]
                result["mou"] = mou_rows.to_dict("records")

            self._json(json.dumps(result, ensure_ascii=False))

        # API: statistik ringkasan
        elif parsed.path == "/api/statistik":
            numeric_cols = ["jml_siswa", "total_rombel", "jml_jurusan"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            stats = {
                "total_smk": len(df),
                "total_siswa": int(df["jml_siswa"].sum()) if "jml_siswa" in df.columns else 0,
                "total_rombel": int(df["total_rombel"].sum()) if "total_rombel" in df.columns else 0,
                "total_mou": len(df_mou) if df_mou is not None else 0,
                "per_kabupaten": df.groupby("kab_kota").size().to_dict(),
                "per_status": df.groupby("status").size().to_dict() if "status" in df.columns else {},
                "per_akreditasi": df.groupby("akreditasi").size().to_dict() if "akreditasi" in df.columns else {},
            }
            self._json(json.dumps(stats, ensure_ascii=False))

        # Serve index.html
        elif parsed.path == "/" or parsed.path == "/index.html":
            if HTML_TEMPLATE.exists():
                content = HTML_TEMPLATE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "index.html tidak ditemukan di templates/")
        else:
            super().do_GET()

    def _json(self, data: str):
        encoded = data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # Suppress request logs


os.makedirs("templates", exist_ok=True)
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("", PORT), APIServer) as httpd:
    print(f"\n🌐 Server berjalan di: http://localhost:{PORT}")
    print("   Tekan Ctrl+C untuk stop\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server dihentikan")
