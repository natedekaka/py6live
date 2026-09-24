import asyncio
import hmac
import os
import random
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ALFABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PANJANG_KODE = 5
KODE_GURU = os.getenv("KODE_GURU", "rahasianate")


@dataclass
class Ruang:
    kode: str
    teks: str = ""
    rev: int = 0
    baris_guru: int = 1
    guru: Optional[WebSocket] = None
    nama_guru: str = ""
    siswa: dict = field(default_factory=dict)
    kunci: asyncio.Lock = field(default_factory=asyncio.Lock)


rooms: dict[str, Ruang] = {}


def buat_kode() -> str:
    while True:
        kode = "".join(random.choice(ALFABET) for _ in range(PANJANG_KODE))
        if kode not in rooms:
            return kode


async def kirim(ws: WebSocket, data: dict) -> bool:
    try:
        await ws.send_json(data)
        return True
    except Exception:
        return False


async def siarkan(ruang: Ruang, data: dict, kecuali: Optional[set] = None) -> None:
    kecuali = kecuali or set()
    async with ruang.kunci:
        target: list[WebSocket] = []
        if ruang.guru is not None:
            target.append(ruang.guru)
        target.extend(ruang.siswa.values())
    if not target:
        return
    hasil = await asyncio.gather(*[kirim(t, data) for t in target if t not in kecuali])
    mati = [t for t, ok in zip(target, hasil) if not ok and t not in kecuali]
    if mati:
        async with ruang.kunci:
            for t in mati:
                if t is ruang.guru:
                    ruang.guru = None
                else:
                    for k, v in list(ruang.siswa.items()):
                        if v is t:
                            ruang.siswa.pop(k, None)


app = FastAPI(title="Py6Live")


@app.middleware("http")
async def cache_no_store(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-cache, no-store")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
    return response


class BuatRuangBody(BaseModel):
    kode_guru: str = ""


@app.post("/api/ruang")
async def buat_ruang(body: BuatRuangBody):
    if not hmac.compare_digest(body.kode_guru.strip(), KODE_GURU):
        raise HTTPException(status_code=403, detail="Kode guru salah.")
    kode = buat_kode()
    rooms[kode] = Ruang(kode=kode)
    return {"kode": kode}


@app.websocket("/ws/{kode}")
async def ws_kelas(ws: WebSocket, kode: str):
    await ws.accept()
    kode = kode.upper().strip()
    ruang = rooms.get(kode)
    if ruang is None:
        await kirim(ws, {"tipe": "error", "pesan": "Kode ruang tidak ditemukan."})
        await ws.close()
        return

    peran = None
    nama = ""
    try:
        pesan = await asyncio.wait_for(ws.receive_json(), timeout=15)
    except Exception:
        await ws.close()
        return

    if pesan.get("tipe") != "hello":
        await kirim(ws, {"tipe": "error", "pesan": "Handshake tidak valid."})
        await ws.close()
        return

    peran = pesan.get("peran")
    nama = (pesan.get("nama") or "").strip()[:30]

    async with ruang.kunci:
        if peran == "guru":
            if nama == "":
                nama = "Guru"
            if ruang.guru is not None:
                await kirim(ws, {"tipe": "error", "pesan": "Ruang ini sudah punya guru."})
                await ws.close()
                return
            ruang.guru = ws
            ruang.nama_guru = nama
        elif peran == "siswa":
            if nama == "":
                nama = "Siswa"
            ruang.siswa[nama] = ws
        else:
            await kirim(ws, {"tipe": "error", "pesan": "Peran tidak dikenal."})
            await ws.close()
            return

    jml_guru = 1 if ruang.guru is not None else 0
    jml_siswa = len(ruang.siswa)
    await kirim(
        ws,
        {
            "tipe": "welcome",
            "peran": peran,
            "nama": nama,
            "teks": ruang.teks,
            "rev": ruang.rev,
            "guru": jml_guru,
            "siswa": jml_siswa,
            "daftar": list(ruang.siswa.keys()),
            "baris": ruang.baris_guru,
        },
    )
    await siarkan(
        ruang,
        {"tipe": "peserta", "guru": jml_guru, "siswa": jml_siswa, "daftar": list(ruang.siswa.keys())},
        kecuali={ws},
    )

    try:
        while True:
            pesan = await ws.receive_json()
            if not isinstance(pesan, dict):
                continue
            tipe = pesan.get("tipe")
            if tipe == "update":
                if peran != "guru":
                    continue
                teks = str(pesan.get("teks") or "")
                async with ruang.kunci:
                    ruang.teks = teks
                    ruang.rev += 1
                    rev = ruang.rev
                    if isinstance(pesan.get("baris"), int):
                        ruang.baris_guru = pesan["baris"]
                paket = {"tipe": "update", "teks": teks, "rev": rev}
                if isinstance(pesan.get("baris"), int):
                    paket["baris"] = pesan["baris"]
                await siarkan(ruang, paket, kecuali={ws})
            elif tipe == "ketik":
                if peran != "guru":
                    continue
                await siarkan(ruang, {"tipe": "ketik", "nama": ruang.nama_guru}, kecuali={ws})
            elif tipe == "output":
                if peran != "guru":
                    continue
                await siarkan(ruang, {"tipe": "output", "teks": str(pesan.get("teks") or "")}, kecuali={ws})
            elif tipe == "scroll":
                if peran != "guru":
                    continue
                if isinstance(pesan.get("baris"), int):
                    ruang.baris_guru = pesan["baris"]
                    await siarkan(ruang, {"tipe": "scroll", "baris": pesan["baris"]}, kecuali={ws})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with ruang.kunci:
            if peran == "guru" and ruang.guru is ws:
                ruang.guru = None
            elif peran == "siswa":
                ruang.siswa.pop(nama, None)
        jml_guru = 1 if ruang.guru is not None else 0
        jml_siswa = len(ruang.siswa)
        await siarkan(
            ruang,
            {"tipe": "peserta", "guru": jml_guru, "siswa": jml_siswa, "daftar": list(ruang.siswa.keys())},
            kecuali={ws},
        )
        if peran == "guru":
            await siarkan(
                ruang,
                {"tipe": "guru-keluar", "pesan": f"{nama} menutup kelas. Teks tetap bisa dibaca."},
                kecuali={ws},
            )
        async with ruang.kunci:
            if ruang.guru is None and not ruang.siswa:
                rooms.pop(ruang.kode, None)


app.mount("/", StaticFiles(directory="static", html=True), name="static")