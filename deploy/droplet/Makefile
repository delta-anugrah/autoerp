# Pintasan untuk AutoERP yang jalan di droplet, di dalam Docker.
#
# Makefile di akar repo menyetir bench LOKAL (`cd ~/frappe-bench && bench ...`).
# Di droplet bench itu tidak ada — ia hidup di dalam container. Berkas ini
# memberi nama pendek yang sama untuk perintah yang sama, tanpa mengubah yang
# di akar dan tanpa membuat siapa pun mengetik ulang baris `docker compose
# exec` sepanjang delapan puluh karakter, yang justru sumber salah ketik.
#
# Pasang di /opt/autoerp/Makefile, lalu cukup `make key-new` dari sana.

SITE    ?= app.smagri.id
COMPOSE  = docker compose -f /opt/autoerp/docker-compose.prod.yml
BENCH    = $(COMPOSE) exec -T backend bench --site $(SITE)

# Pengguna API yang dipakai AutoGrade. Sama dengan Makefile akar.
AG_USER ?= autograde@pks.local

.DEFAULT_GOAL := help
.PHONY: help ping status logs key-show key-new admin-new migrate backup restore-test shell company

help:
	@echo "AutoERP di droplet — site $(SITE)"
	@echo ""
	@echo "  make ping         situsnya hidup?"
	@echo "  make status       container mana yang jalan"
	@echo "  make logs         log backend, ikuti"
	@echo "  make company      nama Company yang terpasang"
	@echo ""
	@echo "  make key-show     tampilkan kunci AutoGrade (TIDAK merotasi)"
	@echo "  make key-new      terbitkan kunci AutoGrade — MEROTASI secret"
	@echo "  make admin-new    akun admin pelanggan (cetak tautan reset)"
	@echo ""
	@echo "  make backup       dump + kirim ke R2 (sama dengan cron 02:15)"
	@echo "  make migrate      bench migrate"
	@echo "  make shell        bench console"

ping:
	@curl -fsS https://$(SITE)/api/method/ping || echo "  TIDAK MENJAWAB"

status:
	@$(COMPOSE) ps --format '{{.Name}}\t{{.State}}'

logs:
	@$(COMPOSE) logs -f --tail=100 backend

company:
	@$(BENCH) execute frappe.client.get_list \
		--kwargs '{"doctype":"Company","fields":["name","abbr","default_currency"]}' | tail -1

# `bench execute` mencetak dict sebagai JSON dan string apa adanya — karena itu
# dua bentuk yang berbeda di bawah. Sama persis dengan Makefile akar.
key-show:
	@key=$$($(BENCH) execute frappe.client.get_value \
		--kwargs '{"doctype":"User","fieldname":"api_key","filters":{"name":"$(AG_USER)"}}' \
		| tail -1 | python3 -c 'import json,sys; print(json.load(sys.stdin)["api_key"])') && \
	secret=$$($(BENCH) execute frappe.utils.password.get_decrypted_password \
		--kwargs '{"doctype":"User","name":"$(AG_USER)","fieldname":"api_secret"}' \
		| tail -1) && \
	echo "ERP_URL=https://$(SITE)" && \
	echo "ERP_API_KEY=$$key" && echo "ERP_API_SECRET=$$secret"

# Merotasi. Yang lama langsung mati, jadi konfirmasinya diketik penuh — satu
# huruf bisa terkirim dari riwayat perintah.
key-new:
	@echo "Ini MEROTASI api_secret. AutoGrade yang masih memakai yang lama akan"
	@echo "ditolak 401 sampai .env-nya ikut diganti."
	@printf "Ketik yes untuk lanjut: "; read ans; [ "$$ans" = "yes" ] || { echo "Dibatalkan."; exit 1; }
	@$(BENCH) execute erpnext.palm_mill.setup.create_integration_user \
		--kwargs '{"email": "$(AG_USER)", "full_name": "AutoGrade"}'

admin-new:
	@[ -n "$(EMAIL)" ] || { echo "Pakai: make admin-new EMAIL=admin@pelanggan.co.id NAMA=\"Admin Pabrik\""; exit 1; }
	$(BENCH) execute erpnext.palm_mill.setup.create_admin_user \
		--kwargs '{"email": "$(EMAIL)", "full_name": "$(NAMA)"}'

migrate:
	$(BENCH) migrate

# Jalur yang sama dengan cron, bukan jalur kedua yang bisa diam-diam berbeda.
backup:
	/opt/autoerp/backup.sh && tail -5 /var/log/autoerp/backup.log

shell:
	$(COMPOSE) exec backend bench --site $(SITE) console
