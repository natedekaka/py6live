# Py6Live

Aplikasi live-teaching Python untuk kelas. Guru mengetik kode Python secara real-time, dan siswa melihat ketikan itu langsung di perangkat masing-masing — lengkap dengan sinkronisasi posisi scroll, highlight sintaks, dan tombol "Jalankan" (Python dijalankan di browser guru via Pyodide dalam Web Worker; hasilnya disiarkan ke siswa).

Source code dikembangkan dengan bantuan AI agent untuk pembelajaran di sekolah.

## Fitur

- **Live typing real-time** — ketikan guru tampil di semua siswa (WebSocket).
- **Scroll sync** — siswa otomatis mengikuti posisi baris guru; tombol "Ikuti guru: ON/OFF" untuk membebaskan scroll mandiri.
- **Highlight sintaks Python** (CodeMirror 6) + nomor baris + bungkus baris panjang.
- **Jalankan kode** (guru) — hasil tampil untuk guru dan disiarkan ke siswa; berjalan di browser guru via [Pyodide](https://pyodide.org) (aman, tidak dieksekusi di server).
- **`input()` interaktif** — prompt input muncul di panel hasil run; berfungsi walau aplikasi diakses via HTTP biasa (tanpa HTTPS), karena nilai jawaban direlay lewat server (lihat bagian API).
- **Daftar peserta ala Zoom** — guru melihat nama siswa bergabung di panel samping yang bisa discroll.
- **Indikator "Guru sedang mengetik..."** untuk siswa.
- **Info posisi** — baris/kolom kursor + jumlah baris di status bar.
- **Ruang kelas aman** — buat ruang hanya dengan kode guru rahasia (server-side, tidak bocor ke sisi klien); siswa cukup memasukkan kode ruang + nama.
- **Banyak guru sekaligus** — setiap guru punya ruang sendiri yang berjalan paralel.

## Teknologi

| Bagian | Pilihan |
|--------|---------|
| Backend | Python 3.12 · FastAPI · Uvicorn · WebSocket |
| Frontend | HTML/CSS/JS · CodeMirror 6 · Pyodide 0.26.4 |
| Eksekusi Python | Pyodide (WebAssembly) di browser guru, dalam Web Worker |
| Deployment | Docker Compose / Podman Compose (base Debian `python:3.12-slim`) |

## Struktur Proyek

```
py6live/
├── main.py                # FastAPI: REST (buat ruang, relay stdin) + WebSocket siaran
├── static/index.html      # Frontend satu halaman (CodeMirror 6 + UI input)
├── static/worker.js       # Web Worker: jalankan Python (Pyodide) + relay input()
├── static/pyodide/        # Aset Pyodide, diunduh saat build image (tidak di repo)
├── requirements.txt
├── Dockerfile             # python:3.12-slim (Debian) + unduh aset Pyodide saat build
├── docker-compose.yml     # port 9322 + env KODE_GURU
├── .gitignore
└── .dockerignore
```

## API

| Metode & Path | Fungsi |
|---|---|
| `POST /api/ruang` | Buat ruang baru (body: `kode_guru`); balasan `{"kode": ...}` |
| `POST /api/stdin/{kode}` | Worker menunggu jawaban `input()` (timeout 180 detik) |
| `POST /api/stdin/{kode}/jawab` | Halaman utama mengirim jawaban / pembatalan untuk `input()` |
| `POST /api/stdin/{kode}/reset` | Bersihkan sesi stdin sebuah ruang |
| `WS /ws/{kode}` | WebSocket kelas (update teks, output, peserta, scroll) |

## Cara Instalasi di Server

Prasyarat: server dengan **Docker + Docker Compose** (atau **Podman + podman-compose**).

### 1. Ambil kode

```bash
git clone https://github.com/natedekaka/py6live.git
cd py6live
```

### 2. Atur kode guru (opsional, wajib diubah untuk produksi)

Buka `docker-compose.yml`, ubah nilai rahasia:

```yaml
environment:
  KODE_GURU: "ganti-dengan-kode-rahasia"
```

### 3. Bangun & jalankan

```bash
# Docker
docker compose up -d --build

# atau Podman (rootless)
podman-compose up -d --build
```

Pada tahap build, aset Pyodide (v0.26.4) diunduh ke `static/pyodide/`, sehingga runtime Python tidak bergantung CDN.

Aplikasi berjalan di port **9322**. Cek status:

```bash
docker ps | grep py6live
curl http://localhost:9322/
```

### 4. Publikasikan (opsional)

Aplikasi berfungsi penuh di HTTP polos — termasuk `input()` yang tidak lagi butuh HTTPS — jadi untuk pemakaian dalam LAN cukup akses `http://IP-SERVER:9322/`. Untuk publikasi ke internet, gunakan **reverse-proxy** yang sudah berjalan di server (Caddy/Nginx) dengan **WebSocket aktif**.

Contoh Caddy:

```
py6live.sman6cimahi.sch.id {
    reverse_proxy localhost:9322
}
```

Caddy otomatis mendukung WebSocket. Jika memakai Nginx:

```nginx
server {
    server_name py6live.sman6cimahi.sch.id;

    location / {
        proxy_pass http://localhost:9322;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 5. Pemakaian harian

- Buka halaman (di LAN: `http://IP-SERVER:9322/`; di internet: `https://py6live.sman6cimahi.sch.id`).
- **Guru:** klik "Saya Guru" → masukkan kode guru → bagikan kode ruang/link ke siswa.
- **Siswa:** klik "Saya Siswa" → masukkan kode ruang + nama → lihat ketikan guru real-time.

> Catatan: CodeMirror 6 dimuat dari CDN (jsdelivr), jadi editor butuh akses internet. Pyodide sudah di-self-host di image (`static/pyodide/`). Untuk pemakaian tanpa internet eksternal sama sekali, self-host aset CodeMirror juga.

## Menjalankan Lokal (Development)

```bash
cd py6live
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Aset Pyodide (dibutuhkan, diunduh manual untuk dev)
mkdir -p static/pyodide && cd static/pyodide
for f in pyodide.js pyodide-lock.json python_stdlib.zip pyodide.asm.js pyodide.asm.wasm; do
  curl -LO "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/$f"
done
cd ../..

uvicorn main:app --host 0.0.0.0 --port 9322
```

Buka `http://localhost:9322/` lalu uji dengan dua tab (satu guru, satu siswa).

## Keamanan

- Kode guru hanya disimpan di server (`KODE_GURU`) dan dicek via `POST /api/ruang`. Tidak ada di kode frontend.
- Eksekusi kode Python berjalan di **browser guru** (Pyodide dalam Web Worker), bukan di server — kode sembarangan tidak menyentuh server.
- Relay `input()`: jawaban diikat ke kode ruang + id unik per pemanggilan, dengan timeout 180 detik; sesi dibersihkan otomatis saat ruang ditutup.
- Broadcast (`update`, `scroll`, `output`) hanya bisa dikirim oleh peran guru; sisi server menolak kiriman siswa.
- Nama siswa di-escape di frontend untuk mencegah XSS.