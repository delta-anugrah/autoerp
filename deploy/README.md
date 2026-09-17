# Deploy AutoERP

Dua kotak: konsol AutoGrade jalan di PC pabrik, AutoERP jalan di server. Berkas di
sini hanya mengurus yang kedua.

| Berkas | Untuk apa |
|---|---|
| `apps.json` | Daftar app yang masuk image. Dibaca `build.sh`, bukan oleh bench. |
| `build.sh` | Membangun image lewat `frappe_docker/images/custom`. |
| `droplet/docker-compose.prod.yml` | Yang benar-benar jalan di droplet. |
| `droplet/.env.example` | Contoh; yang asli dibuat **di droplet**, tidak pernah di repo. |

## Kenapa fork ini bernama `erpnext` di dalam image

AutoERP adalah fork ERPNext, jadi bench memasangnya sebagai `apps/erpnext`. `apps.json`
menunjuk ke repo kita, tapi nama app-nya tetap `erpnext` — modul sawitnya ada di
`erpnext/palm_mill/`. Mengganti nama app berarti mengganti seluruh jalur impor.

## Membangun image

```bash
./deploy/build.sh v1.0.0          # tag lokal, untuk uji di Docker Desktop
```

CI melakukan hal yang sama pada tag `vX.Y.Z` — lihat `.github/workflows/deploy.yml`.
Image tidak pernah diberi tag `latest`: droplet selalu di-pin ke versi persis, supaya
"yang jalan sekarang" tidak pernah jadi tebakan.

## Yang TIDAK ada di sini

Tidak ada nginx dan tidak ada sertifikat. Pola droplet yang sudah dipakai
palmgrade-api tetap: nginx milik host yang terminasi 443 dan meneruskan ke
`127.0.0.1:8080`; container tidak pernah membuka port ke publik. Cloudflare tetap
**Full (strict)**.

Langkah di droplet (resize, `.env`, `new-site`, nginx, certbot) ada di runbook
Fase B, bukan di sini — berkas ini hanya yang ikut ke dalam repo.
