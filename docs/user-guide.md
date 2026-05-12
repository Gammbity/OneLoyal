# OneLoyal User Guide

Bu hujjat kompaniya foydalanuvchilari uchun mo‘ljallangan portaldan qanday foydalanishni tushuntiradi.

## 1. Portal nima?

Portal mijozlar uchun shaxsiy sahifa bo‘lib, u yerda foydalanuvchi:

- o‘z kampaniyalarini ko‘radi
- progress holatini tekshiradi
- claim larni kuzatadi
- tarixiy xarid va mukofot ma’lumotlarini ko‘radi

## 2. URL tuzilmasi

Foydalanuvchi portali quyidagi manzilda ochiladi:

- `http://localhost:5173/{company_name}/user`

Bu yerda `{company_name}` kompaniyaning URL da ishlatiladigan nomi bo‘ladi. Masalan, `dusel` kompaniyasi uchun portal `http://localhost:5173/dusel/user` bo‘ladi.

Shu portal orqali foydalanuvchi o‘z kampaniyalari va progressini ko‘radi.

## 3. Portaldan foydalanish

Foydalanuvchi odatda maxsus magic link yoki kompaniya admini bergan kirish havolasi orqali portalga kiradi.

Token bilan havola yuborilgan bo‘lsa, u ochilganda portal sessiyasi avtomatik yaratiladi.

## 4. Kirish usuli

1. Sizga yuborilgan secure link ni oching.
2. Link ichidagi token tekshiriladi.
3. Agar token to‘g‘ri bo‘lsa, portal ochiladi.
4. Agar token noto‘g‘ri yoki muddati o‘tgan bo‘lsa, xatolik chiqadi.

## 5. Portal bo‘limlari

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

## 6. Foydalanuvchi qanday ishlatadi?

1. Magic link orqali portalga kiring.
2. Kampaniyalar ro‘yxatini ko‘ring.
3. Qaysi tier ga yaqin ekaningizni tekshiring.
4. Claim holatlarini kuzating.
5. Xarid tarixini ko‘rib boring.

## 7. Portal menyusi

Portal yuqori menyusida quyidagi bo‘limlar bor:

- Campaigns
- Claims
- Logout

Logout bosilganda portal sessiyasi tozalanadi.

## 8. Til tanlash

Agar admin panelda til yoqilgan bo‘lsa, portal ham tizimning umumiy til sozlamalaridan foydalanishi mumkin.

Mavjud tillar:

- English
- O‘zbekcha
- Русский

## 9. Xatoliklar

Agar portal ochilmasa:

- secure link muddati o‘tgan bo‘lishi mumkin
- token noto‘g‘ri bo‘lishi mumkin
- internet yoki local frontend ishlamayotgan bo‘lishi mumkin

Bunday holda administratorga murojaat qiling.

## 10. Foydali tavsiyalar

- Portal linkni boshqalar bilan ulashmang.
- Maxfiy tokenni saqlang.
- Noma’lum qurilmalarda logout qiling.
