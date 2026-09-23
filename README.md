# Py6Live

Aplikasi live-teaching Python untuk kelas. Guru mengetik kode Python secara real-time, dan siswa melihat ketikan itu langsung di perangkat masing-masing — lengkap dengan sinkronisasi posisi scroll, highlight sintaks, dan tombol "Jalankan" (Python berjalan di browser siswa/guru via Pyodide).

Source code dikembangkan dengan bantuan AI agent untuk pembelajaran di sekolah.

## Fitur

- **Live typing real-time** — ketikan guru tampil di semua siswa (WebSocket).
- **Scroll sync** — siswa otomatis mengikuti posisi baris guru; tombol "Ikuti guru: ON/OFF" untuk membebaskan scroll mandiri.
- **Highlight sintaks Python** (CodeMirror 6) + nomor baris + bungkus baris panjang.
- **Jalankan kode** (guru) — hasil tampil untuk guru dan disiarkan ke siswa; berjalan di browser via [Pyodide](https://pyodide.org) (aman, tidak dieksekusi di server).
- **Daftar peserta ala Zoom** — guru melihat nama siswa bergabung di panel samping yang bisa discroll.
- **Indikator "Guru sedang mengetik..."** untuk siswa.
- **Info posisi** — baris/kolom kursor + jumlah baris di status bar.
- **Ruang kelas aman** — buat ruang hanya dengan kode guru rahasia (server-side, tidak bocor ke sisi klien); siswa cukup memasukkan kode ruang + nama.
- **Banyak guru sekaligus** — setiap guru punya ruang sendiri yang berjalan paralel.

## Teknologi

| Bagian | Pilihan |
|--------|---------|
| Backend | Python 3.12 · FastAPI · Uvicorn · WebSocket |
| Frontend | HTML/CSS/JS · CodeMirror 6 · Pyodide |
| Eksekusi Python | Pyodide (WebAssembly) di masing-masing browser |
| Deployment | Docker · Docker Compose (base Debian `python:3.12-slim`) |

## Struktur Proyek

```
py6live/
├── main.py                # FastAPI: REST buat ruang + WebSocket siaran real-time
├── static/index.html      # Frontend satu halaman (CodeMirror 6 + Pyodide)
├── requirements.txt
├── Dockerfile             # python:3.12-slim (Debian)
├── docker-compose.yml     # port 9322 + env KODE_GURU
├── .gitignore
└── .dockerignore
```

## Cara Instalasi di Server

Prasyarat: server dengan **Docker** dan **Docker Compose** terpasang.

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
docker compose up -d --build
```

Aplikasi berjalan di port **9322**. Cek status:

```bash
docker ps | grep py6live
curl http://localhost:9322/
```

### 4. Publikasikan ke internet

Gunakan **reverse-proxy** yang sudah berjalan di server (Caddy/Nginx) dengan **WebSocket aktif**.

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

- Buka halaman (mis. `https://py6live.sman6cimahi.sch.id`).
- **Guru:** klik "Saya Guru" → masukkan kode guru → bagikan kode ruang/link ke siswa.
- **Siswa:** klik "Saya Siswa" → masukkan kode ruang + nama → lihat ketikan guru real-time.

> Catatan: CodeMirror dan Pyodide dimuat dari CDN (jsdelivr). Siswa dan guru perlu akses internet. Untuk pemakaian tanpa internet eksternal, self-host aset-aset tersebut.

## Menjalankan Lokal (Development)

```bash
cd py6live
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9322
```

Buka `http://localhost:9322/` lalu uji dengan dua tab (satu guru, satu siswa).

## Keamanan

- Kode guru hanya disimpan di server (`KODE_GURU`) dan dicek via `POST /api/ruang`. Tidak ada di kode frontend.
- Eksekusi kode Python berjalan di **browser** siswa/guru (Pyodide), bukan di server — kode sembarangan tidak menyentuh server.
- Broadcast (`update`, `scroll`, `output`) hanya bisa dikirim oleh peran guru; sisi server menolak kiriman siswa.
- Nama siswa di-escape di frontend untuk mencegah XSS.