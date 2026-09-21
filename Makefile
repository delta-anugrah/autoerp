# Developer shortcuts for the local bench running this app.
#
# The bench is NOT this repo. This app is installed into a bench as
# `apps/erpnext`, and the bench lives outside the working tree — by default
# ~/frappe-bench. Every target below therefore drives $(BENCH), not `.`.
# Override per machine:
#
#     make up BENCH=/srv/frappe-bench SITE=pks.localhost
#
# ...or write them once into Makefile.local (gitignored) and just `make up`.
#
# Setting a bench up from scratch is docs/installation.md; this file only drives
# one that already exists.

# Per-machine settings live in Makefile.local, which is gitignored. Write the
# bench and site once and every target below picks them up, so `make up` alone
# is enough:
#
#     $ cat Makefile.local
#     BENCH = $(HOME)/autoerp-bench
#     SITE  = autoerp.localhost
#
# `-include` is silent when the file is absent, and because it is read before
# the `?=` defaults, whatever it sets wins.
-include Makefile.local

BENCH ?= $(HOME)/frappe-bench
SITE  ?= pks.localhost
PORT  ?= 8000
URL    = http://$(SITE):$(PORT)

# The API user AutoGrade authenticates as (docs/autograde-integration.md §3).
AG_USER ?= autograde@pks.local

# `bench start` runs its processes under honcho. That one process is the
# reliable "is the bench up?" signal: the web worker alone can be restarting,
# and the redis ports stay bound by children.
SUPERVISOR = honcho start
BOOT_LOG   = $(BENCH)/logs/bench-start.log

.DEFAULT_GOAL := help
.PHONY: help up start stop down restart status ping key-show key-new admin-new migrate backup shell where \
        demo demo-reset demo-off reset-data reset-data-fresh

help:
	@echo "Bench: $(BENCH)   Site: $(SITE)   $(URL)"
	@echo
	@echo "  make up         start in the background, wait until the site answers"
	@echo "  make start      start in the foreground (Ctrl-C to stop), logs on screen"
	@echo "  make stop       stop the running bench"
	@echo "  make restart    stop, then up"
	@echo "  make status     what is running, and whether the site answers"
	@echo "  make key-show   print the AutoGrade API key:secret WITHOUT rotating it"
	@echo "  make key-new    create/rotate the AutoGrade integration user (kills the old secret)"
	@echo "  make admin-new  buat admin pelanggan (EMAIL=... NAMA=...)"
	@echo "  make demo       isi data demo untuk showcase ke klien"
	@echo "  make demo-reset hapus data demo lalu isi ulang bersih"
	@echo "  make demo-off   hapus data demo, berhenti di situ (sesudah showcase)"
	@echo "  make migrate    bench migrate"
	@echo "  make backup     database + files backup"
	@echo "  make shell      bench console (python REPL on the site)"
	@echo "  make where      which checkout this bench actually runs"

# Starting a second bench is the failure this file exists to prevent: redis
# cannot bind its ports, one child dies, and honcho then SIGTERMs the whole
# group — which reads on screen as "bench crashed" while the FIRST bench is
# still happily serving.
# One shell block on purpose: make runs every recipe LINE in its own shell, so
# an `exit` in a guard on its own line only ends that line and the rest of the
# target still runs — which is how an early version of this target started the
# second bench it was written to prevent.
up:
	@if pgrep -f "$(SUPERVISOR)" >/dev/null; then \
		echo "Already running (pid $$(pgrep -f "$(SUPERVISOR)" | tr '\n' ' ' | sed 's/ $$//')) — $(URL)"; \
	else \
		mkdir -p "$(BENCH)/logs"; \
		( cd "$(BENCH)" && nohup bench start >"$(BOOT_LOG)" 2>&1 & ); \
		printf "Starting bench"; \
		ok=0; \
		for i in $$(seq 1 60); do \
			sleep 2; \
			if curl -fsS -m 2 -o /dev/null "$(URL)/api/method/ping" 2>/dev/null; then ok=1; break; fi; \
			if ! pgrep -f "$(SUPERVISOR)" >/dev/null; then break; fi; \
			printf "."; \
		done; \
		if [ $$ok -eq 1 ]; then echo " — up at $(URL)"; else \
			echo " — FAILED. Last lines of $(BOOT_LOG):"; tail -20 "$(BOOT_LOG)"; exit 1; \
		fi; \
	fi

start:
	@if pgrep -f "$(SUPERVISOR)" >/dev/null; then \
		echo "Already running (pid $$(pgrep -f "$(SUPERVISOR)" | tr '\n' ' ' | sed 's/ $$//')) — $(URL)"; \
		exit 1; \
	fi; \
	cd "$(BENCH)" && exec bench start

# SIGTERM the supervisor, not the children: honcho stops the whole group on the
# way out, so redis releases its ports.
stop:
	@pids=$$(pgrep -f "$(SUPERVISOR)" | tr '\n' ' '); \
	if [ -z "$$pids" ]; then echo "Not running."; exit 0; fi; \
	kill $$pids; \
	for i in $$(seq 1 15); do \
		pgrep -f "$(SUPERVISOR)" >/dev/null || { echo "Stopped."; exit 0; }; \
		sleep 1; \
	done; \
	echo "Still alive after 15s (pid $$(pgrep -f "$(SUPERVISOR)" | tr '\n' ' ')) — kill -9 by hand."; exit 1

down: stop

# Sequenced through sub-makes rather than `restart: stop up`, which `make -j`
# is free to run at the same time.
restart:
	@$(MAKE) --no-print-directory stop
	@$(MAKE) --no-print-directory up

status:
	@pids=$$(pgrep -f "$(SUPERVISOR)" | tr '\n' ' '); \
	if [ -n "$$pids" ]; then echo "bench    running (pid $${pids%% })"; else echo "bench    stopped"; fi
	@if curl -fsS -m 3 -o /dev/null "$(URL)/api/method/ping" 2>/dev/null; \
		then echo "site     answering at $(URL)"; \
		else echo "site     NOT answering at $(URL)"; fi
	@printf "apps     "; cat "$(BENCH)/sites/apps.txt" 2>/dev/null | tr '\n' ' '; echo
	@$(MAKE) --no-print-directory where

# Which clone the bench actually serves. It is easy to end up editing a second
# checkout of this repo and wonder why nothing changes.
where:
	@printf "app      "; \
	if [ -d "$(BENCH)/apps/erpnext" ]; then \
		cd "$(BENCH)/apps/erpnext" && echo "$$(pwd) @ $$(git rev-parse --short HEAD) ($$(git branch --show-current))"; \
	else echo "$(BENCH)/apps/erpnext not found"; fi

# Reads the existing credentials back, in a form that pastes straight into the
# AutoGrade console's .env. Use this instead of re-running the setup command:
# creating the user again rotates api_secret, and every client still holding the
# old one starts failing with 401.
#
# `bench execute` prints a dict as JSON and a string raw, hence the two shapes.
key-show:
	@cd "$(BENCH)" && \
	key=$$(bench --site $(SITE) execute frappe.client.get_value \
		--kwargs '{"doctype":"User","fieldname":"api_key","filters":{"name":"$(AG_USER)"}}' \
		| tail -1 | python3 -c 'import json,sys; print(json.load(sys.stdin)["api_key"])') && \
	secret=$$(bench --site $(SITE) execute frappe.utils.password.get_decrypted_password \
		--kwargs '{"doctype":"User","name":"$(AG_USER)","fieldname":"api_secret"}' \
		| tail -1) && \
	echo "ERP_API_KEY=$$key" && echo "ERP_API_SECRET=$$secret"

key-new:
	@echo "This ROTATES api_secret — anything still using the old one breaks."
	@printf "Type yes to continue: "; read ans; [ "$$ans" = "yes" ] || { echo "Aborted."; exit 1; }
	@cd "$(BENCH)" && bench --site $(SITE) execute erpnext.palm_mill.setup.create_integration_user \
		--kwargs '{"email": "$(AG_USER)", "full_name": "AutoGrade"}'

# Akun administrator milik pelanggan, supaya `Administrator` bisa dikunci setelah
# pemasangan. Yang dicetak adalah tautan reset, bukan kata sandi: kata sandi akan
# tertinggal di riwayat terminal dan di jendela chat tempat ia ditempelkan.
admin-new:
	@[ -n "$(EMAIL)" ] || { echo "Pakai: make admin-new EMAIL=admin@pelanggan.co.id NAMA=\"Admin Pelanggan\""; exit 1; }
	@[ -n "$(NAMA)" ]  || { echo "Pakai: make admin-new EMAIL=admin@pelanggan.co.id NAMA=\"Admin Pelanggan\""; exit 1; }
	cd "$(BENCH)" && bench --site $(SITE) execute erpnext.palm_mill.setup.create_admin_user \
		--kwargs '{"email": "$(EMAIL)", "full_name": "$(NAMA)"}'

# Data demo untuk showcase ke klien. Platnya sama persis dengan seeder AutoGrade
# (`autograde/scripts/seed-console-demo.py`), jadi satu truk adalah truk yang sama
# di dua layar — ganti plat di satu sisi berarti ganti di sisi lain, PR yang sama.
#
# `demo_mode` di site_config adalah SAKLARNYA: seeder menolak jalan tanpa itu, dan
# penolakan itu yang menghalangi satu salah ketik `--site` menanam data demo ke
# situs produksi. `make demo` menyalakannya untuk site ini.
demo:
	cd "$(BENCH)" && bench --site $(SITE) set-config demo_mode 1 \
		&& bench --site $(SITE) execute erpnext.palm_mill.demo.seed

demo-reset:
	cd "$(BENCH)" && bench --site $(SITE) execute erpnext.palm_mill.demo.reset

# Hapus tiket demo dan BERHENTI — beda dari demo-reset yang langsung mengisi ulang.
# Jalankan sesudah showcase, dan sebelum ada yang menguji data sungguhan di site ini:
# baris demo duduk di tabel yang sama dengan yang asli, jadi daftar tiket yang masih
# membawanya terbaca seolah pabrik membukukan muatan yang tidak pernah diterima.
# Master (supplier, truk, blok, user) sengaja dibiarkan — sama seperti demo-reset.
demo-off:
	cd "$(BENCH)" && bench --site $(SITE) execute erpnext.palm_mill.demo.off

migrate:
	cd "$(BENCH)" && bench --site $(SITE) migrate

# HAPUS SEMUA DATA di site ini, lalu pasang ulang app dari nol.
#
#   make reset-data          lihat dulu: site mana, berapa isinya. Tidak menghapus
#   make reset-data-fresh    hapus sungguhan (minta konfirmasi ketik)
#
# Perintahnya `bench reinstall`, BUKAN `drop-site`: site-nya tetap ada beserta
# `site_config.json` (kunci API AutoGrade, kata sandi database, setelan surat),
# yang dibuang isinya. `drop-site` menghapus semuanya termasuk berkas itu, dan
# memasang ulangnya berarti menerbitkan kunci baru — AutoGrade di PC pabrik akan
# ditolak 401 sampai `ERP_KEY`-nya ikut diganti.
#
# Yang hilang, semuanya PERMANEN dan tanpa backup:
#   - seluruh tiket, kunjungan truk, Purchase Receipt, dan jurnalnya;
#   - master: supplier, truk, blok, item, akun;
#   - semua user KECUALI Administrator, termasuk akun operator dan `make admin-new`;
#   - berkas unggahan di `sites/$(SITE)/private` dan `/public`.
#
# Sandi Administrator kembali ke `admin`. Kunci integrasi AutoGrade ikut hilang
# bersama user-nya — terbitkan lagi dengan `make key-new` sesudahnya, dan pasang
# hasilnya di `.env` AutoGrade.
#
# ⚠️ JANGAN di site produksi. Ini alat untuk site uji coba, atau site baru
# sebelum dipakai sungguhan. Sesudahnya: `make migrate` lalu `make key-new`.
reset-data:
	@echo "Site   : $(SITE)"
	@echo "Bench  : $(BENCH)"
	@echo ""
	@cd "$(BENCH)" && bench --site $(SITE) execute frappe.client.get_count \
		--args "['Purchase Receipt']" 2>/dev/null \
		| sed 's/^/  Purchase Receipt : /' || true
	@echo ""
	@echo "Akan menghapus PERMANEN (tanpa backup): seluruh tiket dan jurnalnya,"
	@echo "master (supplier, truk, blok, item, akun), semua user selain Administrator,"
	@echo "dan berkas unggahan. Sandi Administrator kembali ke 'admin', dan kunci"
	@echo "integrasi AutoGrade harus diterbitkan lagi ('make key-new')."
	@echo ""
	@echo "Kalau memang itu yang diinginkan: make reset-data-fresh"

# Konfirmasi diketik, bukan ditekan — pola yang sama dengan AutoGrade. Satu huruf
# bisa terkirim dari riwayat perintah atau sentuhan tak sengaja; satu kata tidak.
# Nama site ikut diketik, karena `make reset-data-fresh SITE=...` yang salah tunjuk
# adalah cara paling mudah mengosongkan site yang keliru.
reset-data-fresh:
	@echo "SEMUA data di site $(SITE) akan dihapus permanen, tanpa backup."
	@echo "Jalankan 'make reset-data' dulu kalau ingin melihat rinciannya."
	@echo ""
	@printf "Ketik nama site untuk melanjutkan ($(SITE)): "
	@read jawab; [ "$$jawab" = "$(SITE)" ] || { echo "Dibatalkan."; exit 1; }
	cd "$(BENCH)" && bench --site $(SITE) reinstall --yes --admin-password admin
	@echo ""
	@echo "Site kosong. Lanjutkan: make migrate, lalu make key-new untuk kunci AutoGrade."

backup:
	cd "$(BENCH)" && bench --site $(SITE) backup --with-files

shell:
	cd "$(BENCH)" && bench --site $(SITE) console
