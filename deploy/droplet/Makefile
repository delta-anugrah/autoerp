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
.PHONY: help ping status logs key-show key-new admin-new migrate backup restore-test shell company db-grants

help:
	@echo "AutoERP di droplet — site $(SITE)"
	@echo ""
	@echo "  make ping         situsnya hidup?"
	@echo "  make status       container mana yang jalan"
	@echo "  make logs         log backend, ikuti"
	@echo "  make company      nama Company yang terpasang"
	@echo "  make db-grants    izin DB ikut IP container yang berubah — WAJIB tiap site baru"
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

# Izin database yang tidak mati saat container dibuat ulang.
#
# `bench new-site` memberi GRANT ke HOST tempat ia kebetulan berjalan saat itu --
# sebuah alamat IP container, mis. `_d6ea..@172.20.0.7`. Alamat itu milik jaringan
# Docker dan BERUBAH setiap container dibuat ulang: deploy, `compose up
# --force-recreate`, bahkan reboot droplet biasa. Begitu berubah, grant-nya tidak
# cocok lagi dan SELURUH situs menjawab:
#
#     MySQLdb.OperationalError: (1045, "Access denied for user '_d6ea...'@'172.20.0.9'")
#
# Sudah terjadi 2026-09-21 malam: `app.` dan `demo.` dua-duanya mati 500 sesudah
# deploy, dan pesannya terbaca seperti sandi salah, bukan seperti alamat berubah.
#
# ⚠️ Aman memakai `%`: port 3306 TIDAK dipublikasikan ke luar (`docker inspect`
# menunjukkan `"3306/tcp": null`), jadi `%` di sini berarti "mana pun di dalam
# jaringan Docker ini", bukan "dari internet". Sandinya tetap sandi per-situs yang
# dibuat Frappe, dan dibaca dari `site_config.json` -- tidak ada yang diketik.
#
# Idempoten: `CREATE USER IF NOT EXISTS` + `GRANT`, jadi aman dijalankan ulang.
db-grants:
	@pw=$$(grep '^DB_PASSWORD=' /opt/autoerp/.env | cut -d= -f2-) && \
	for s in $$($(COMPOSE) exec -T backend sh -c \
		'for d in sites/*/; do [ -f "$$d/site_config.json" ] && basename "$$d"; done' \
		| tr -d '\r'); do \
		db=$$($(COMPOSE) exec -T backend python -c \
			"import json;print(json.load(open('sites/$$s/site_config.json'))['db_name'])" | tr -d '\r') && \
		dbpw=$$($(COMPOSE) exec -T backend python -c \
			"import json;print(json.load(open('sites/$$s/site_config.json'))['db_password'])" | tr -d '\r') && \
		$(COMPOSE) exec -T mariadb mariadb -uroot -p"$$pw" -e \
			"CREATE USER IF NOT EXISTS '$$db'@'%' IDENTIFIED BY '$$dbpw'; \
			 GRANT ALL PRIVILEGES ON \`$$db\`.* TO '$$db'@'%'; FLUSH PRIVILEGES;" && \
		echo "$$s -> $$db OK"; \
	done

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
