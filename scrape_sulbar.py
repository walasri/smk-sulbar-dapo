#!/usr/bin/env python3
"""
Scraper Data SMK Sulawesi Barat dari DAPO Kemendikdasmen
Sumber: https://smk.kemendikdasmen.go.id

Penggunaan:
  python scrape_sulbar.py              # Scrape data dasar 125 SMK Sulbar
  python scrape_sulbar.py --detail     # Termasuk jurusan & MOU (lebih lambat)
"""

import requests
import csv
import json
import time
import argparse
import os
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://smk.kemendikdasmen.go.id"
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

PROVINSI = "Prov. Sulawesi Barat"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}


def get_sekolah_list():
    """Ambil daftar semua SMK di Sulawesi Barat."""
    resp = requests.get(
        f"{BASE_URL}/api/sekolah",
        params={"provinsi": PROVINSI},
        headers=HEADERS,
        timeout=15
    )
    data = resp.json()
    return data.get("data", [])


def scrape_jurusan(uid):
    """Scrape daftar jurusan aktif dari halaman detail sekolah."""
    url = f"{BASE_URL}/detail-sekolah/{uid}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = text.split("\n")

        jurusan_list = []
        in_section = False
        for line in lines:
            line = line.strip()
            if "Rombongan Belajar per Kompetensi" in line:
                in_section = True
                continue
            if in_section:
                if "JUMLAH" in line or "Peserta Didik per Tingkat" in line:
                    break
                skip = ["Kompetensi Keahlian", "Tingkat I", "Tingkat II",
                        "Tingkat III", "Tingkat IV", "Total Rombel", ""]
                if line in skip:
                    continue
                if line and not line.replace(" ", "").isdigit() and len(line) > 5:
                    jurusan_list.append(line)
        return jurusan_list
    except Exception:
        return []


def scrape_mou(uid):
    """Scrape data MOU/DUDI dari halaman detail sekolah."""
    import re
    base_url = f"{BASE_URL}/detail-sekolah/{uid}"
    all_mou = []
    try:
        r = requests.get(base_url, headers=HEADERS, timeout=15)
        mou_pages = re.findall(r"mou_page=(\d+)", r.text)
        max_page = max([int(p) for p in mou_pages], default=1)

        for page in range(1, max_page + 1):
            url = f"{base_url}?mou_page={page}" if page > 1 else base_url
            if page > 1:
                r = requests.get(url, headers=HEADERS, timeout=15)
                time.sleep(0.3)
            soup = BeautifulSoup(r.text, "html.parser")
            for t in soup.find_all("table"):
                hdrs = [th.get_text(strip=True) for th in t.find_all("th")]
                if "Nama Mitra DUDI" in hdrs or "Bentuk Kerjasama" in hdrs:
                    for row in t.find_all("tr")[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all("td")]
                        if cells and len(cells) >= 4 and cells[0].isdigit():
                            all_mou.append({
                                "nama_mitra": cells[1] if len(cells) > 1 else "",
                                "bentuk_kerjasama": cells[2] if len(cells) > 2 else "",
                                "bidang_usaha": cells[3] if len(cells) > 3 else "",
                                "status": cells[4] if len(cells) > 4 else "",
                            })
                    break
    except Exception:
        pass
    return all_mou


def main():
    parser = argparse.ArgumentParser(
        description="Scraper Data SMK Sulawesi Barat - DAPO Kemendikdasmen"
    )
    parser.add_argument("--detail", action="store_true",
                        help="Scrape jurusan dan MOU per sekolah (lebih lambat)")
    args = parser.parse_args()

    print("=" * 60)
    print("Scraper Data SMK Sulawesi Barat")
    print("Sumber: smk.kemendikdasmen.go.id")
    print("=" * 60)

    print(f"\n⏳ Mengambil daftar SMK di {PROVINSI}...")
    sekolah_list = get_sekolah_list()
    print(f"✓ Ditemukan {len(sekolah_list)} SMK\n")

    results = []
    mou_results = []

    for i, s in enumerate(sekolah_list, 1):
        uid = s["sekolah_id"]
        nama = s["nama"]

        row = {
            "npsn": s["npsn"],
            "nama": nama,
            "status": "Negeri" if s["status_sekolah"] == "1" else "Swasta",
            "akreditasi": s.get("akreditasi", ""),
            "kab_kota": s.get("kab_kota", ""),
            "provinsi": s.get("provinsi", ""),
            "alamat": s.get("alamat_jalan", ""),
            "lintang": s.get("lintang", ""),
            "bujur": s.get("bujur", ""),
            "jml_siswa": s.get("jml_siswa", 0),
            "total_rombel": s.get("total_rombel", 0),
            "jml_jurusan": s.get("jml_jurusan", 0),
            "jurusan": "",
            "url": f"{BASE_URL}/detail-sekolah/{uid}",
        }

        if args.detail:
            jurusan = scrape_jurusan(uid)
            row["jurusan"] = " | ".join(jurusan)
            row["jml_jurusan_aktif"] = len(jurusan)

            mou_list = scrape_mou(uid)
            for m in mou_list:
                mou_results.append({
                    "npsn": s["npsn"],
                    "nama_sekolah": nama,
                    "kab_kota": s.get("kab_kota", ""),
                    **m
                })
            print(f"[{i:3d}/{len(sekolah_list)}] ✓ {nama} — {len(jurusan)} jurusan, {len(mou_list)} MOU")
            time.sleep(0.4)
        else:
            print(f"[{i:3d}/{len(sekolah_list)}] ✓ {nama}")

        results.append(row)

    # Simpan CSV sekolah
    sekolah_file = OUTPUT_DIR / "smk_sulbar_lengkap.csv"
    fieldnames = list(results[0].keys()) if results else []
    with open(sekolah_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n✓ Data sekolah disimpan: {sekolah_file} ({len(results)} baris)")

    # Simpan CSV MOU jika detail
    if args.detail and mou_results:
        mou_file = OUTPUT_DIR / "smk_sulbar_mou.csv"
        with open(mou_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(mou_results[0].keys()))
            writer.writeheader()
            writer.writerows(mou_results)
        print(f"✓ Data MOU disimpan: {mou_file} ({len(mou_results)} baris)")

    print("\n✅ Selesai!")


if __name__ == "__main__":
    main()
