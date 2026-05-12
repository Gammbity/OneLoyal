# OneLoyal Admin Guide

Bu hujjat OneLoyal tizimining umumiy admin paneli va kompaniya admin paneli qanday ishlashini tushuntiradi.

## 1. Talablar

- Docker va Docker Compose o‘rnatilgan bo‘lishi kerak.
- Git repozitoriya lokal kompyuterga yuklangan bo‘lishi kerak.
- Tavsiya etilgan brauzer: Chrome yoki Edge.

## 2. Rol va URL tuzilmasi

Tizimda 3 ta asosiy kirish nuqtasi bo‘ladi:

- `http://localhost:5173/admin` - umumiy admin panel
- `http://localhost:5173/{company_name}/admin` - kompaniya admin paneli
- `http://localhost:5173/{company_name}/user` - kompaniya foydalanuvchi portali

Bu yerda `{company_name}` kompaniya nomi yoki undan hosil qilingan URL qismi bo‘ladi. Masalan, global admin `dusel` kompaniyasini yaratsa, kompaniya paneli `http://localhost:5173/dusel/admin` bo‘ladi.

Umumiy admin panel faqat kompaniyalarni kuzatish va boshqarish uchun ishlatiladi. Bu panelda:

- kompaniyalar yaratiladi
- kompaniya login/paroli beriladi
- kompaniya holati kuzatiladi
- texnik jarayonlar nazorat qilinadi

Global admin panelda sovg‘a, user yoki kompaniya ichki biznes sozlamalari boshqarilmaydi.

Kompaniya admini o‘ziga berilgan login va parol bilan `/{company_name}/admin` ga kiradi. Shu yerda u:

- ERP tizimini ulaydi
- integratsiyalarni sozlaydi
- sovg‘a tier larini belgilaydi
- import va sync jarayonlarini boshqaradi

Kompaniya yaratish paytida kerak bo‘ladigan asosiy ma’lumotlar:

- kompaniya nomi
- login
- parol

## 3. Loyihani ishga tushirish

Loyihaning ildiz papkasida quyidagini bajaring:

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

Tizim ishga tushgach quyidagi servislar ochiladi:

- API: `http://localhost:8000`
- Frontend admin panel: `http://localhost:5173`
- PostgreSQL va Redis konteynerlari ichki tarmoqda ishlaydi.

## 4. Umumiy admin panelga kirish

1. Brauzerda `http://localhost:5173/admin` ni oching.
2. Login formaga admin email va parolini kiriting.
3. Tizimga kirgach kompaniyalar ro‘yxati va boshqaruv paneli ochiladi.

Bu paneldan yangi kompaniya yaratiladi, kompaniya statusi nazorat qilinadi va kerak bo‘lsa kirish ma’lumotlari qayta beriladi.

## 5. Umumiy admin panel bo‘limlari

### Companies

- Yangi kompaniya yaratish
- Kompaniya holatini boshqarish
- Kompaniya admin login ma’lumotlarini ko‘rish yoki qayta chiqarish

### Platform Control

- Tizimdagi barcha kompaniyalarni kuzatish
- Muammoli kompaniyalarni bloklash yoki faollashtirish
- Umumiy statistikani ko‘rish

## 6. Kompaniya admin panelga kirish

1. Kompaniya admini uchun yaratilgan login va parolni oling.
2. Brauzerda `http://localhost:5173/{company_name}/admin` ni oching.
3. Login ma’lumotlarini kiriting.
4. Kompaniyangizning ERP sozlamalari ochiladi.

Kompaniya admini o‘z tashkilotining ichki sozlamalarini boshqaradi. U boshqa kompaniyalarni ko‘rmaydi.

Misol:

- kompaniya: `dusel`
- admin login: `dusel@gmail.com`
- admin parol: `dusel123`
- kirish URL: `http://localhost:5173/dusel/admin`

## 7. Kompaniya admin panel bo‘limlari

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

## 8. Kompaniya admin uchun asosiy ish oqimi

1. Umumiy admin tomonidan kompaniya yaratiladi.
2. Kompaniya adminiga login va parol beriladi.
3. Admin `dusel/admin` ga kiradi.
4. ERP yoki integratsiya ulanadi.
5. Kampaniya va gift tier lar sozlanadi.
6. Import, sync va claims ishlari boshqariladi.

## 9. API bilan ishlash

Admin panel API bilan `http://localhost:8000/api/v1` prefiksi orqali ishlaydi.

Muhim endpoint lar:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/register-company`
- `GET /api/v1/campaigns`
- `GET /api/v1/customers`
- `GET /api/v1/reports/*`

## 10. Til sozlamalari

Admin panelda til tanlash mavjud:

- English
- O‘zbekcha
- Русский

Tanlangan til brauzer xotirasida saqlanadi va sahifa yangilangandan keyin ham qoladi.

## 11. Nosozliklarni tekshirish

Agar tizim ochilmasa:

- `docker compose ps` bilan konteynerlar holatini tekshiring.
- `docker compose logs api --tail 80` bilan API loglarini ko‘ring.
- `docker compose logs frontend --tail 80` bilan frontend loglarini ko‘ring.
- `.env` faylida DB va Redis manzillarini tekshiring.

## 12. Tavsiya etilgan xavfsizlik amaliyoti

- Production muhitda standart parollarni ishlatmang.
- `SECRET_KEY` va `ENCRYPTION_KEY` ni albatta almashtiring.
- Admin akkauntlarni faqat ishonchli foydalanuvchilarga bering.
