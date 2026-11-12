# Oqim

Logistika va ta’minot zanjirini boshqarish tizimi.

Muallif: Komiljonov Abdunurbek, KI-301, 2026.

Ombordagi mahsulotlar, ta’minotchilar, mijoz buyurtmalari va jo‘natmalar bitta dasturda yuritiladi. Interfeys o‘zbek tilida. Narxlar butun so‘mda, vaqt UTC bo‘yicha saqlanadi.

## Ishga tushirish

Windows PowerShell oynasida loyiha papkasiga o‘ting va bajaring:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Parolni kiriting. Brauzerda http://127.0.0.1:8080 manzilini oching. Python 3.12 yoki yangiroq versiya kerak. Birinchi ishga tushirishda kutubxonalar internetdan olinadi. Keyingi ishga tushirishlarda shu parolni qayta kiritish mumkin. Mahalliy SECRET_KEY har ishga tushganda yangilanadi va eski seanslar tugaydi.

Linux yoki macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
read -rsp 'Administrator password: ' ADMIN_PASSWORD
export ADMIN_PASSWORD
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
flask --app app:create_app seed
python app.py
```

## Bo‘limlar

Umumiy holat sahifasida ombor qiymati, faol buyurtmalar va kam qolgan mahsulotlar ko‘rinadi. Ombor bo‘limida mahsulot qo‘shish, qidirish, kirim kiritish va CSV olish mumkin. Buyurtmaga bir nechta mahsulot kiritiladi. Miqdor yetmasa, buyurtma butunlay rad etiladi. Saqlanganda mahsulot ombordan ajratiladi.

Holatlar: Yangi → Yolda → Yetkazildi. Faqat yangi buyurtma bekor qilinadi va uning mahsulotlari omborga qaytadi. Jo‘natishda haydovchi va transport raqami yoziladi. Bu qo‘lda yuritiladigan hisob; GPS kuzatuvi yo‘q.

Boshlang‘ich yozuvlar ishlashni ko‘rsatish uchun tuzilgan namunalardir. Ular Kaggle yoki haqiqiy korxona ma’lumotlari sifatida ko‘rsatilmagan. Bo‘sh baza bilan boshlash uchun seed buyrug‘ini bajarmang. GCP startup skripti namuna yozuvlarini bir marta qo‘shadi.

## Tuzilishi

| Fayl | Vazifasi |
|---|---|
| app.py | Marshrutlar, sessiya, tekshiruvlar va hisob amallari |
| schema.sql | Oltita jadval va bog‘lanishlar |
| templates/ | Jinja sahifalari |
| static/ | CSS va buyurtma qatorlari uchun JavaScript |
| tests/test_app.py | Hisob qoidalarini tekshirish |
| Dockerfile | Gunicorn bilan konteyner |
| cloud/ | Google Cloud uchun ishga tushirish skriptlari |
| docs/ | Hisobot va UML sxemalari |

## Tekshirish

```bash
python -m unittest discover -s tests -v
```

Sinovlar alohida vaqtinchalik bazada bajariladi. Asosiy bazaga tegmaydi.

## Google Cloud

Hisobda billing yoqilgan bo‘lishi kerak. Deploy skripti pullik VM, disk va tashqi IP yaratadi. Amaldagi xarajat GCP konsolida tekshiriladi. VM o‘chirilganida ham saqlangan disk va ajratilgan IP uchun to‘lov qolishi mumkin.

Repozitoriy ochiq bo‘lishi va Dockerfile uning ildizida turishi kerak. Cloud Shell oynasida repozitoriyni klonlang, ichiga o‘ting va ishga tushiring:

```bash
bash cloud/deploy-gcp.sh
```

Skript project ID va GitHub HTTPS manzilini so‘raydi. Batafsil tartib START_HERE_RU.txt faylida.

## Sozlamalar

| O‘zgaruvchi | Qiymat |
|---|---|
| ADMIN_PASSWORD | Kirish paroli, majburiy |
| SECRET_KEY | Sessiya imzosi; bulutda doimiy tasodifiy qiymat |
| DATABASE | Mahalliy data/logistics.db, konteynerda /data/logistics.db |
| COOKIE_SECURE | HTTPS joylashtirishda 1 |
| TRUST_PROXY | Faqat taqdim etilgan yopiq Caddy → ilova tarmog‘ida 1 |

Bulutda baza /var/lib/oqim papkasida, konteynerdan tashqarida saqlanadi. Bitta VM va bitta ilova nusxasi ishlatiladi. Katta yuklama, ko‘p ombor, buxgalteriya integratsiyasi va foydalanuvchi rollari ushbu versiyaga kiritilmagan.

## Manbalar

- https://flask.palletsprojects.com/en/stable/deploying/gunicorn/
- https://flask.palletsprojects.com/en/stable/web-security/
- https://docs.cloud.google.com/compute/docs/instances/startup-scripts/linux
- https://docs.cloud.google.com/compute/docs/containers/deploying-containers
- https://caddyserver.com/docs/automatic-https
- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
