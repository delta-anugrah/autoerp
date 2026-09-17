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
# Setting a bench up from scratch is docs/dev-setup.md; this file only drives
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
.PHONY: help up start stop down restart status ping key-show key-new migrate backup shell where

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

migrate:
	cd "$(BENCH)" && bench --site $(SITE) migrate

backup:
	cd "$(BENCH)" && bench --site $(SITE) backup --with-files

shell:
	cd "$(BENCH)" && bench --site $(SITE) console
