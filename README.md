# SMK Sulawesi Barat — Data DAPO

Data dan dashboard interaktif SMK se-Sulawesi Barat, bersumber dari DAPO Kemendikdasmen.

## Fitur

- **Scraper** — ambil data 125 SMK Sulbar langsung dari portal DAPO
- **Dashboard Web** — tampilan interaktif dengan filter kabupaten, status, akreditasi, dan jurusan
- **API lokal** — endpoint JSON untuk integrasi data
- **Data lengkap** — sekolah, jurusan, dan MOU/DUDI

## Struktur Repo

```
smk-sulbar-dapo/
├── scrape_sulbar.py      # Scraper data dari DAPO Kemendikdasmen
├── generate_web.py       # Server dashboard web lokal (port 8000)
├── requirements.txt      # Dependensi Python
├── templates/
│   └── index.html        # Tampilan dashboard
└── data/
    ├── smk_sulbar_lengkap.csv   # Data utama 125 SMK
    ├── smk_sulbar_jurusan.csv   # Data jurusan per sekolah
    └── smk_sulbar_mou.csv       # Data MOU/DUDI per sekolah
```

## Instalasi

```bash
git clone https://github.com/username/smk-sulbar-dapo.git
cd smk-sulbar-dapo
pip install -r requirements.txt
```

## Penggunaan

### 1. Scrape Data

Ambil data dasar (cepat):
```bash
python scrape_sulbar.py
```

Termasuk jurusan dan MOU per sekolah (lebih lambat):
```bash
python scrape_sulbar.py --detail
```

### 2. Jalankan Dashboard

```bash
python generate_web.py
```

Buka browser: [http://localhost:8000](http://localhost:8000)

## API Endpoint

Server lokal menyediakan beberapa endpoint JSON:

| Endpoint | Deskripsi |
|---|---|
| `GET /api/meta` | Metadata (daftar kabupaten, jurusan) |
| `GET /api/sekolah` | Daftar sekolah dengan filter |
| `GET /api/detail?npsn=...` | Detail sekolah by NPSN |
| `GET /api/statistik` | Statistik ringkasan |

### Filter `/api/sekolah`

```
/api/sekolah?kab_kota=Kab. Majene
/api/sekolah?status=Negeri
/api/sekolah?akreditasi=A
/api/sekolah?jurusan=Teknik Komputer
/api/sekolah?q=smkn
```

## Data

| File | Isi | Jumlah |
|---|---|---|
| `smk_sulbar_lengkap.csv` | Data utama sekolah | 125 SMK |
| `smk_sulbar_jurusan.csv` | Jurusan per sekolah | 75+ jurusan |
| `smk_sulbar_mou.csv` | MOU/DUDI per sekolah | 3.373 MOU |

**Kolom data utama:** `npsn`, `nama`, `status`, `akreditasi`, `kab_kota`, `provinsi`, `alamat`, `lintang`, `bujur`, `jml_siswa`, `total_rombel`, `jml_jurusan`

## Kabupaten

Data mencakup 6 kabupaten di Sulawesi Barat:

- Kab. Mamuju
- Kab. Polewali Mandar
- Kab. Majene
- Kab. Mamasa
- Kab. Pasangkayu
- Kab. Mamuju Tengah

## Sumber Data

- Portal DAPO: [smk.kemendikdasmen.go.id](https://smk.kemendikdasmen.go.id)
- Kementerian Pendidikan Dasar dan Menengah RI
- Data disinkronkan: April 2026

## Lisensi

Data bersumber dari portal publik pemerintah (DAPO Kemendikdasmen).
