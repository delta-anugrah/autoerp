#!/usr/bin/env python3
"""Satukan aset hasil build ke folder yang benar-benar dilayani saat runtime.

Dijalankan **saat image dibangun**, sesudah `bench build`.

## Kenapa ini perlu

Image dasar punya `entrypoint.sh` yang, tiap container start, menghapus
`sites/assets` lalu menggantinya dengan symlink ke `frappe-bench/assets`:

    rm -rf sites/assets && ln -s /home/frappe/frappe-bench/assets sites/assets

Sementara `bench build` menulis ke `sites/assets`. Selama build keduanya folder
terpisah, jadi tanpa langkah ini hasil build dibuang begitu container jalan.

Gagalnya tidak terlihat: `assets.json` di `assets/` tetap bawaan image dasar dan
menunjuk berkas yang sudah tidak ada, jadi Desk memuat bundle lama dari cache —
tanpa error, tanpa 404. Terbukti di produksi 2026-09-22.

## Kenapa peta DIGABUNG, bukan ditimpa

Peta hasil build cuma memuat kunci milik erpnext (8), sementara peta di `assets/`
memuat seluruh app (44), termasuk `desk.bundle.js` milik frappe. Menimpanya
membuat Desk kehilangan bundle-nya sendiri dan berhenti memuat apa pun —
ketahuan saat langkah ini disimulasikan di dalam image sebelum dirilis.
"""

import json
import pathlib
import shutil
import sys

BENCH = pathlib.Path("/home/frappe/frappe-bench")
SUMBER = BENCH / "sites/assets"  # ke mana `bench build` menulis
TUJUAN = BENCH / "assets"  # dari mana runtime membaca
PETA = ("assets.json", "assets-rtl.json")


def gabung_peta(nama: str) -> int:
	"""Timpa per-kunci, bukan per-berkas. Mengembalikan jumlah kunci hasil gabung."""
	sumber, tujuan = SUMBER / nama, TUJUAN / nama
	if not sumber.exists():
		return 0

	lama = json.loads(tujuan.read_text()) if tujuan.exists() else {}
	baru = json.loads(sumber.read_text())
	hasil = {**lama, **baru}

	tujuan.parent.mkdir(parents=True, exist_ok=True)
	tujuan.write_text(json.dumps(hasil, indent=1))
	print(f"  {nama}: {len(lama)} + {len(baru)} -> {len(hasil)} kunci")
	return len(hasil)


def salin_berkas() -> None:
	"""Semua selain peta. Peta diurus `gabung_peta` supaya tidak saling menimpa.

	⚠️ Sebagian entri di `sites/assets/` adalah **symlink yang sudah menunjuk ke
	`assets/`** — `bench build` menautkannya, bukan menyalin. Menyalinnya berarti
	menyalin berkas ke dirinya sendiri, dan `shutil` berhenti dengan "are the same
	file" untuk ratusan berkas sekaligus. Yang seperti itu dilewati: isinya memang
	sudah berada di tujuan.
	"""
	for item in sorted(SUMBER.iterdir()):
		if item.name in PETA:
			continue

		tujuan = TUJUAN / item.name
		if item.resolve() == tujuan.resolve():
			print(f"  lewati {item.name} (sudah menunjuk tujuan)")
			continue

		if item.is_dir():
			shutil.copytree(item, tujuan, dirs_exist_ok=True, symlinks=False)
		else:
			shutil.copy2(item, tujuan)
		print(f"  salin {item.name}")


def main() -> int:
	if not SUMBER.exists():
		print(f"TIDAK ADA {SUMBER} — `bench build` gagal?", file=sys.stderr)
		return 1

	print(f"Menyatukan {SUMBER} -> {TUJUAN}")
	salin_berkas()
	for nama in PETA:
		gabung_peta(nama)

	# Peta yang menunjuk berkas hantu adalah persis kegagalan yang bikin masalah
	# ini tidak ketahuan berhari-hari, jadi diperiksa di sini selagi build masih
	# bisa dibatalkan.
	peta = json.loads((TUJUAN / "assets.json").read_text())
	hilang = [
		f"{k} -> {v}"
		for k, v in peta.items()
		# `/assets/x` dilayani dari `TUJUAN/x` — saat runtime `sites/assets`
		# cuma symlink ke sana.
		if v.startswith("/assets/") and not (TUJUAN / v[len("/assets/") :]).exists()
	]
	if hilang:
		print("PETA MENUNJUK BERKAS YANG TIDAK ADA:", file=sys.stderr)
		for baris in hilang:
			print("  " + baris, file=sys.stderr)
		return 1

	print(f"OK — {len(peta)} kunci, semuanya menunjuk berkas yang ada")
	return 0


if __name__ == "__main__":
	sys.exit(main())
