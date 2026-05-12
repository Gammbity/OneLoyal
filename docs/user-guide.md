# OneLoyal User Guide

Bu hujjat OneLoyal portalidan oddiy foydalanuvchi sifatida qanday foydalanish bo‘yicha qo‘llanma hisoblanadi.

## 1. Portal nima?

Portal mijozlar uchun shaxsiy sahifa bo‘lib, u yerda foydalanuvchi:

- o‘z kampaniyalarini ko‘radi
- progress holatini tekshiradi
- claim larni kuzatadi
- tarixiy xarid va mukofot ma’lumotlarini ko‘radi

## 2. Portaldan foydalanish

Foydalanuvchi odatda maxsus magic link orqali portalga kiradi.

Portal URL odatda quyidagicha bo‘ladi:

- `http://localhost:5173/portal`
- `http://localhost:5173/portal/access`

Agar sizga token bilan havola yuborilgan bo‘lsa, u ochilganda portal sessiyasi avtomatik yaratiladi.

## 3. Kirish usuli

1. Sizga yuborilgan secure link ni oching.
2. Link ichidagi token tekshiriladi.
3. Agar token to‘g‘ri bo‘lsa, portal ochiladi.
4. Agar token noto‘g‘ri yoki muddati o‘tgan bo‘lsa, xatolik chiqadi.

## 4. Portal bo‘limlari

### Campaigns

Bu yerda sizga tegishli kampaniyalar ko‘rsatiladi.

Har bir kampaniya uchun:

- kampaniya nomi
- status
- progress
- mukofot bosqichlari

### Campaign detail

Kampaniya ichiga kirganda quyidagilarni ko‘rishingiz mumkin:

- jami xarid summasi
- keyingi tier ga qancha qolganligi
- qaysi mukofotga yaqin ekanligingiz

### Claims

Bu bo‘limda barcha claim lar ko‘rinadi:

- pending
- approved
- rejected
- skipped

## 5. Foydalanuvchi qanday ishlatadi?

1. Magic link orqali portalga kiring.
2. Kampaniyalar ro‘yxatini ko‘ring.
3. Qaysi tier ga yaqin ekaningizni tekshiring.
4. Claim holatlarini kuzating.
5. Xarid tarixini ko‘rib boring.

## 6. Portal menyusi

Portal yuqori menyusida quyidagi bo‘limlar bor:

- Campaigns
- Claims
- Logout

Logout bosilganda portal sessiyasi tozalanadi.

## 7. Til tanlash

Agar admin panelda til yoqilgan bo‘lsa, portal ham tizimning umumiy til sozlamalaridan foydalanishi mumkin.

Mavjud tillar:

- English
- O‘zbekcha
- Русский

## 8. Xatoliklar

Agar portal ochilmasa:

- secure link muddati o‘tgan bo‘lishi mumkin
- token noto‘g‘ri bo‘lishi mumkin
- internet yoki local frontend ishlamayotgan bo‘lishi mumkin

Bunday holda administratorga murojaat qiling.

## 9. Foydali tavsiyalar

- Portal linkni boshqalar bilan ulashmang.
- Maxfiy tokenni saqlang.
- Noma’lum qurilmalarda logout qiling.
