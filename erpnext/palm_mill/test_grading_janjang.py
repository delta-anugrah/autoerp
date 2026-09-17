# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Tiap baris Sortasi membawa jumlah janjangnya, bukan cuma persen dan berat.

Dibaca sebagai sumber, bukan dijalankan lawan database: runner Frappe tidak bisa
jalan di setiap mesin, dan yang dijaga di sini semuanya terbaca dari kode.

AutoGrade sudah lama mengirim angkanya (`counts` membawa `mentah`,
`tangkai_panjang`, `acc`, `rej`, `total`); sebelum ini API cuma memakai tiga
terakhir untuk field header dan membuang sisanya. Jadi yang berubah cuma di sisi
AutoERP — nol perubahan kontrak.

Dua hal yang gampang salah dan karena itu dipatok:

* **Matang tidak diukur kamera.** Persennya diturunkan (`100 − mentah − tangkai −
  lainnya`), jadi jumlahnya juga harus diturunkan: `acc − tangkai_panjang`. Kalau
  diambil dari `counts["matang"]` yang tidak pernah dikirim, angkanya selalu 0 dan
  terbaca seolah tidak ada buah matang sama sekali.
* **Tangkai Panjang adalah bagian dari ACC**, bukan kategori keempat. `acc` sudah
  memuatnya, jadi Matang harus menguranginya — kalau tidak, penjumlahan tiap baris
  melebihi `grading_total` dan angkanya tidak pernah cocok dengan tiket.
"""

import ast
import json
import pathlib
import unittest

AKAR = pathlib.Path(__file__).resolve().parent
API = AKAR / "api.py"
DOCTYPE = AKAR / "doctype" / "weighbridge_grading" / "weighbridge_grading.json"
TIKET = AKAR / "doctype" / "weighbridge_ticket" / "weighbridge_ticket.json"


def _fungsi(nama):
	pohon = ast.parse(API.read_text(encoding="utf-8"))
	for simpul in ast.walk(pohon):
		if isinstance(simpul, ast.FunctionDef) and simpul.name == nama:
			return simpul
	raise AssertionError(f"api.py tidak punya fungsi {nama}()")


class TestKolomJanjang(unittest.TestCase):
	def test_child_doctype_punya_kolom_janjang(self):
		d = json.loads(DOCTYPE.read_text(encoding="utf-8"))
		nama = {f["fieldname"] for f in d["fields"]}

		self.assertIn("janjang", nama)
		self.assertIn("janjang", d["field_order"])

	def test_janjang_int_dan_terlihat_di_grid(self):
		"""Buah dihitung satuan, bukan pecahan — dan gunanya cuma kalau kelihatan
		tanpa harus membuka tiap baris."""
		d = json.loads(DOCTYPE.read_text(encoding="utf-8"))
		f = next(f for f in d["fields"] if f["fieldname"] == "janjang")

		self.assertEqual(f["fieldtype"], "Int")
		self.assertEqual(f.get("in_list_view"), 1)

	def test_api_mengisi_janjang_tiap_baris(self):
		sumber = ast.unparse(_fungsi("_apply_grading"))

		self.assertIn("janjang", sumber)

	def test_matang_diturunkan_dari_acc_dikurangi_tangkai(self):
		"""Kamera tidak pernah menghitung `matang`; `acc` sudah memuat tangkai panjang."""
		sumber = ast.unparse(_fungsi("_apply_grading"))

		self.assertIn("acc", sumber)
		self.assertIn("tangkai_panjang", sumber)

	def test_janjang_tidak_pernah_negatif(self):
		"""`acc − tangkai_panjang` bisa negatif kalau angkanya tidak sinkron, dan
		jumlah buah negatif di layar krani terbaca seperti kerusakan."""
		sumber = ast.unparse(_fungsi("_apply_grading"))

		self.assertIn("max(0", sumber.replace(" ", ""))


class TestBagianHasilSortasi(unittest.TestCase):
	"""Angka hasil kerja naik dari tab Integrasi ke bagiannya sendiri.

	Sebelum ini `grading_total/acc/rej` duduk di balik lipatan bernama
	"Integration", berdampingan dengan id teknis milik support — dan itu membuat
	orang tidak tahu angkanya ada sama sekali (ketemu 2026-09-17 saat uji truk).
	"""

	def setUp(self):
		self.d = json.loads(TIKET.read_text(encoding="utf-8"))
		self.by = {f["fieldname"]: f for f in self.d["fields"]}
		self.urut = self.d["field_order"]

	def _bagian_dari(self, fieldname):
		"""Label Section Break terakhir sebelum field ini."""
		label = None
		for n in self.urut:
			f = self.by.get(n, {})
			if f.get("fieldtype") == "Section Break":
				label = f.get("label")
			if n == fieldname:
				return label
		raise AssertionError(f"{fieldname} tidak ada di field_order")

	def test_angka_grading_tidak_lagi_di_bagian_integrasi(self):
		for n in ("grading_total", "grading_acc", "grading_rej"):
			self.assertNotIn(str(self._bagian_dari(n)).lower(), ("integration", "integrasi"), n)

	def test_id_teknis_tetap_di_integrasi(self):
		"""Jejak support tidak ikut pindah: itu yang dipakai melacak sengketa."""
		for n in ("autograde_visit_id", "autograde_assignment_id", "scale_ticket_no"):
			self.assertIn(str(self._bagian_dari(n)).lower(), ("integration", "integrasi"), n)

	def test_angka_grading_muncul_sebelum_tabel_sortasi(self):
		"""Supaya terbaca satu alur: 4 janjang -> 1 ACC/3 REJ -> Mentah 75%."""
		self.assertLess(self.urut.index("grading_total"), self.urut.index("grading"))

	def test_urutan_kolom_hasil_sortasi(self):
		"""Kiri: Total Janjang lalu Diterima. Kanan: Sortasi Diterima lalu Ditolak.

		Dipatok karena urutan dua kolom itu gampang tertukar waktu menambah field
		baru, dan tertukar berarti Diterima berdampingan dengan Ditolak — dua angka
		yang mirip bentuknya, dibaca sekilas oleh krani.
		"""
		i = self.urut.index("sb_hasil_sortasi")
		self.assertEqual(
			self.urut[i : i + 6],
			[
				"sb_hasil_sortasi",
				"grading_total",
				"grading_acc",
				"col_hasil_sortasi",
				"grading_received_at",
				"grading_rej",
			],
		)

	def test_bagian_baru_tidak_terlipat(self):
		"""Kalau `collapsible`, angkanya tersembunyi lagi — persis masalah semula."""
		bagian = self._bagian_dari("grading_total")
		sb = next(
			f for f in self.d["fields"] if f.get("fieldtype") == "Section Break" and f.get("label") == bagian
		)

		self.assertNotEqual(sb.get("collapsible"), 1)


class TestTataLetakSortasi(unittest.TestCase):
	"""Tabel Sortasi selebar halaman, angkanya dua kolom di bawahnya.

	Column Break yang tidak ditutup Section Break membuat SEMUA field sesudahnya
	ikut terjepit di kolom kanan — tabel Sortasi jadi setengah lebar dan kolom
	Berat terpotong jadi "Berat (...". Itu yang terlihat di layar 2026-09-17.
	"""

	def setUp(self):
		self.d = json.loads(TIKET.read_text(encoding="utf-8"))
		self.by = {f["fieldname"]: f for f in self.d["fields"]}
		self.urut = self.d["field_order"]

	def _tipe(self, n):
		return self.by.get(n, {}).get("fieldtype")

	def test_tabel_sortasi_mulai_di_bagian_sendiri(self):
		"""Section Break sebelum `grading` mengakhiri dua kolom di atasnya, jadi
		tabelnya dapat lebar penuh."""
		i = self.urut.index("grading")
		sebelum = [n for n in self.urut[:i] if self._tipe(n) in ("Section Break", "Column Break")]

		self.assertEqual(self._tipe(sebelum[-1]), "Section Break")

	def test_angka_uang_dibagi_dua_kolom(self):
		"""Kiri: sampah, potongan, netto. Kanan: harga, nilai, entri."""
		i = self.urut.index("sampah_kg")
		j = self.urut.index("harga_per_kg")
		antara = [n for n in self.urut[i:j] if self._tipe(n) == "Column Break"]

		self.assertEqual(len(antara), 1, "harus tepat satu Column Break antara netto dan harga")

	def test_urutan_kiri_dan_kanan_sesuai_permintaan(self):
		i = self.urut.index("sampah_kg")
		ekor = [n for n in self.urut[i:] if self._tipe(n) not in ("Section Break", "Tab Break")]
		kolom = ekor.index(next(n for n in ekor if self._tipe(n) == "Column Break"))

		self.assertEqual(ekor[:kolom], ["sampah_kg", "potongan_pct", "net_after_deduction_kg"])
		self.assertEqual(ekor[kolom + 1 : kolom + 4], ["harga_per_kg", "nilai", "purchase_receipt"])
