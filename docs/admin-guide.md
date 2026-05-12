# OneLoyal Admin Guide

Bu hujjat OneLoyal tizimini administrator sifatida ishga tushirish va ishlatish bo‘yicha qo‘llanma hisoblanadi.

## 1. Talablar

- Docker va Docker Compose o‘rnatilgan bo‘lishi kerak.
- Git repozitoriya lokal kompyuterga yuklangan bo‘lishi kerak.
- Tavsiya etilgan brauzer: Chrome yoki Edge.

## 2. Loyihani ishga tushirish

Loyihaning ildiz papkasida quyidagini bajaring:

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

Tizim ishga tushgach quyidagi servislar ochiladi:

- API: `http://localhost:8000`
- Frontend admin panel: `http://localhost:5173`
- PostgreSQL va Redis konteynerlari ichki tarmoqda ishlaydi.

## 3. Admin panelga kirish

1. Frontend sahifasini oching: `http://localhost:5173`
2. Login formaga admin email va parolini kiriting.
3. Tizimga kirgach boshqaruv paneli ochiladi.

Agar siz test muhitida ishlayotgan bo‘lsangiz, oldin yaratilgan admin akkauntdan foydalaning.

## 4. Admin panel bo‘limlari

### Dashboard

- Umumiy ko‘rsatkichlar
- Faol kampaniyalar soni
- Mijozlar statistikasi
- Mukofot va claim holati

### Campaigns

Bu bo‘limda kampaniyalar boshqariladi:

- Yangi kampaniya yaratish
- Boshlanish va tugash sanalarini belgilash
- Valyutani sozlash
- Kampaniya holatini ko‘rish va tahrirlash

### Gift Tiers

- Mukofot bosqichlarini yaratish
- Minimal xarid miqdorini belgilash
- Zaxira va tracking rejimlarini boshqarish

### Customers

- Mijozlar ro‘yxati
- Xarid progressi
- Qaysi tierga yaqinligi

### Imports

- CSV fayl orqali savdo yoki mijoz ma’lumotlarini yuklash
- Oldindan ko‘rish
- Xatolarni tekshirish
- Importni tasdiqlash

### Integrations

- Tashqi integratsiyalarni ulash
- MoySklad, CSV, manual yoki boshqa provayderlarni boshqarish
- Sozlamalar JSON ni tahrirlash

### Sync

- Sinxronizatsiya jarayonlarini kuzatish
- Qo‘lda sync ishga tushirish
- Kechikkan yoki to‘xtab qolgan sync larni tiklash

### Claims

- Mukofot so‘rovlarini ko‘rish
- Tasdiqlash yoki rad etish
- Claim holatini tekshirish

### Reports

- Kampaniya natijalari
- Top mijozlar
- Gift liability
- Sales va sync hisobotlari

### Operations

- Texnik operatsiyalar
- Qolib ketgan sync larni tiklash
- Notification processing holatini kuzatish

## 5. Admin uchun asosiy ish oqimi

1. Kampaniya yarating.
2. Kampaniya uchun gift tier lar qo‘shing.
3. Mijozlar va savdo ma’lumotlarini import qiling.
4. Progress va reports bo‘limida natijalarni tekshiring.
5. Integratsiyalarni ulang va sync ni yoqing.
6. Claim larni tasdiqlang yoki rad eting.

## 6. API bilan ishlash

Admin panel API bilan `http://localhost:8000/api/v1` prefiksi orqali ishlaydi.

Muhim endpoint lar:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/register-company`
- `GET /api/v1/campaigns`
- `GET /api/v1/customers`
- `GET /api/v1/reports/*`

## 7. Til sozlamalari

Admin panelda til tanlash mavjud:

- English
- O‘zbekcha
- Русский

Tanlangan til brauzer xotirasida saqlanadi va sahifa yangilangandan keyin ham qoladi.

## 8. Nosozliklarni tekshirish

Agar tizim ochilmasa:

- `docker compose ps` bilan konteynerlar holatini tekshiring.
- `docker compose logs api --tail 80` bilan API loglarini ko‘ring.
- `docker compose logs frontend --tail 80` bilan frontend loglarini ko‘ring.
- `.env` faylida DB va Redis manzillarini tekshiring.

## 9. Tavsiya etilgan xavfsizlik amaliyoti

- Production muhitda standart parollarni ishlatmang.
- `SECRET_KEY` va `ENCRYPTION_KEY` ni albatta almashtiring.
- Admin akkauntlarni faqat ishonchli foydalanuvchilarga bering.
