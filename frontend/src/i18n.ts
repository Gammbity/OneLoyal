export type Language = "en" | "uz" | "ru";

export const translations: Record<Language, Record<string, string>> = {
  en: {
    // Auth
    "auth.login": "Login",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.registerCompany": "Register Company",
    "auth.companyName": "Company Name",
    "auth.companySlug": "Company Slug",
    "auth.ownerFullName": "Full Name",
    "auth.ownerEmail": "Email",
    "auth.ownerPassword": "Password",
    "auth.login_button": "Sign In",
    "auth.logout": "Logout",
    "auth.invalidCredentials": "Invalid email or password",
    "auth.sessionExpired": "Session expired. Please login again.",

    // Navigation
    "nav.dashboard": "Dashboard",
    "nav.campaigns": "Campaigns",
    "nav.gift.tiers": "Gift Tiers",
    "nav.customers": "Customers",
    "nav.imports": "Imports",
    "nav.integrations": "Integrations",
    "nav.claims": "Reward Claims",
    "nav.reports": "Reports",
    "nav.ops": "Operations",

    // Common
    "common.search": "Search",
    "common.filter": "Filter",
    "common.add": "Add",
    "common.edit": "Edit",
    "common.delete": "Delete",
    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.loading": "Loading...",
    "common.error": "Error",
    "common.success": "Success",
    "common.actions": "Actions",
    "common.status": "Status",
    "common.date": "Date",
    "common.empty": "No data",

    // Campaigns
    "campaigns.title": "Campaigns",
    "campaigns.newCampaign": "New Campaign",
    "campaigns.name": "Campaign Name",
    "campaigns.startDate": "Start Date",
    "campaigns.endDate": "End Date",
    "campaigns.currency": "Currency",
    "campaigns.status": "Status",
    "campaigns.totalCustomers": "Total Customers",
    "campaigns.active": "Active",
    "campaigns.archived": "Archived",

    // Customers
    "customers.title": "Customers",
    "customers.name": "Customer Name",
    "customers.email": "Email",
    "customers.phone": "Phone",
    "customers.totalPurchases": "Total Purchases",
    "customers.progress": "Progress",

    // Reports
    "reports.title": "Reports",
    "reports.overview": "Overview",
    "reports.topCustomers": "Top Customers",
    "reports.giftLiability": "Gift Liability",
    "reports.claims": "Claims",
    "reports.sales": "Sales",
    "reports.qualified": "Qualified",
    "reports.claims_count": "Claims",
    "reports.purchaseAmount": "Purchase Amount",
    "reports.reachedTier": "Reached Tier",
    "reports.activeClaims": "Active Claims",

    // Integrations
    "integrations.title": "Integrations",
    "integrations.newIntegration": "New Integration",
    "integrations.provider": "Provider",
    "integrations.name": "Name",
    "integrations.status": "Status",
    "integrations.active": "Active",
    "integrations.draft": "Draft",
    "integrations.error": "Error",

    // Import
    "import.title": "Import",
    "import.uploadFile": "Upload File",
    "import.preview": "Preview",
    "import.confirm": "Confirm Import",
    "import.rows": "Rows",
    "import.errors": "Errors",

    // Settings
    "settings.title": "Settings",
    "settings.companySettings": "Company Settings",
    "settings.userManagement": "User Management",
    "settings.notificationPreferences": "Notification Preferences",
  },

  uz: {
    // Auth
    "auth.login": "Kirish",
    "auth.email": "Email",
    "auth.password": "Parol",
    "auth.registerCompany": "Kompaniya Ro'yxatdan O'tkazish",
    "auth.companyName": "Kompaniya Nomi",
    "auth.companySlug": "Kompaniya Slugi",
    "auth.ownerFullName": "To'liq Ismi",
    "auth.ownerEmail": "Email",
    "auth.ownerPassword": "Parol",
    "auth.login_button": "Kirish",
    "auth.logout": "Chiqish",
    "auth.invalidCredentials": "Noto'g'ri email yoki parol",
    "auth.sessionExpired": "Sessiya tugadi. Iltimos, qayta kiring.",

    // Navigation
    "nav.dashboard": "Asosiy Panel",
    "nav.campaigns": "Kampaniyalar",
    "nav.gift.tiers": "Sovg'a Darajalari",
    "nav.customers": "Mijozlar",
    "nav.imports": "Yuklash",
    "nav.integrations": "Integrations",
    "nav.claims": "Mukofotlash Davolashlar",
    "nav.reports": "Hisobotlar",
    "nav.ops": "Operatsiyalar",

    // Common
    "common.search": "Qidirish",
    "common.filter": "Filtr",
    "common.add": "Qo'shish",
    "common.edit": "Tahrirlash",
    "common.delete": "O'chirish",
    "common.save": "Saqlash",
    "common.cancel": "Bekor qilish",
    "common.loading": "Yuklanmoqda...",
    "common.error": "Xato",
    "common.success": "Muvaffaqiyat",
    "common.actions": "Harakatlar",
    "common.status": "Holati",
    "common.date": "Sana",
    "common.empty": "Ma'lumot yo'q",

    // Campaigns
    "campaigns.title": "Kampaniyalar",
    "campaigns.newCampaign": "Yangi Kampaniya",
    "campaigns.name": "Kampaniya Nomi",
    "campaigns.startDate": "Boshlanish Sanasi",
    "campaigns.endDate": "Tugash Sanasi",
    "campaigns.currency": "Valyuta",
    "campaigns.status": "Holati",
    "campaigns.totalCustomers": "Jami Mijozlar",
    "campaigns.active": "Faol",
    "campaigns.archived": "Arxivlangan",

    // Customers
    "customers.title": "Mijozlar",
    "customers.name": "Mijoz Nomi",
    "customers.email": "Email",
    "customers.phone": "Telefon",
    "customers.totalPurchases": "Jami Xaridlar",
    "customers.progress": "Taraqqiyot",

    // Reports
    "reports.title": "Hisobotlar",
    "reports.overview": "Umumiy Ko'rinish",
    "reports.topCustomers": "Eng Yaxshi Mijozlar",
    "reports.giftLiability": "Sovg'a Mas'uliyati",
    "reports.claims": "Davolashlar",
    "reports.sales": "Sotuvlar",
    "reports.qualified": "Malakali",
    "reports.claims_count": "Davolashlar",
    "reports.purchaseAmount": "Xarid Summasi",
    "reports.reachedTier": "Erishgan Daraja",
    "reports.activeClaims": "Faol Davolashlar",

    // Integrations
    "integrations.title": "Integrations",
    "integrations.newIntegration": "Yangi Integration",
    "integrations.provider": "Provayder",
    "integrations.name": "Nomi",
    "integrations.status": "Holati",
    "integrations.active": "Faol",
    "integrations.draft": "Qoralama",
    "integrations.error": "Xato",

    // Import
    "import.title": "Yuklash",
    "import.uploadFile": "Fayl Yuklash",
    "import.preview": "Oldindan Ko'rish",
    "import.confirm": "Yuklashni Tasdiqlash",
    "import.rows": "Qatorlar",
    "import.errors": "Xatolar",

    // Settings
    "settings.title": "Sozlamalar",
    "settings.companySettings": "Kompaniya Sozlamalari",
    "settings.userManagement": "Foydalanuvchi Boshqaruvi",
    "settings.notificationPreferences": "Bildirishnoma Parametrlari",
  },

  ru: {
    // Auth
    "auth.login": "Вход",
    "auth.email": "Email",
    "auth.password": "Пароль",
    "auth.registerCompany": "Зарегистрировать компанию",
    "auth.companyName": "Название компании",
    "auth.companySlug": "Слаг компании",
    "auth.ownerFullName": "Полное имя",
    "auth.ownerEmail": "Email",
    "auth.ownerPassword": "Пароль",
    "auth.login_button": "Войти",
    "auth.logout": "Выход",
    "auth.invalidCredentials": "Неправильный email или пароль",
    "auth.sessionExpired": "Сеанс истёк. Пожалуйста, войдите снова.",

    // Navigation
    "nav.dashboard": "Главная",
    "nav.campaigns": "Кампании",
    "nav.gift.tiers": "Уровни подарков",
    "nav.customers": "Клиенты",
    "nav.imports": "Импорт",
    "nav.integrations": "Интеграции",
    "nav.claims": "Претензии по вознаграждениям",
    "nav.reports": "Отчёты",
    "nav.ops": "Операции",

    // Common
    "common.search": "Поиск",
    "common.filter": "Фильтр",
    "common.add": "Добавить",
    "common.edit": "Редактировать",
    "common.delete": "Удалить",
    "common.save": "Сохранить",
    "common.cancel": "Отмена",
    "common.loading": "Загрузка...",
    "common.error": "Ошибка",
    "common.success": "Успешно",
    "common.actions": "Действия",
    "common.status": "Статус",
    "common.date": "Дата",
    "common.empty": "Нет данных",

    // Campaigns
    "campaigns.title": "Кампании",
    "campaigns.newCampaign": "Новая кампания",
    "campaigns.name": "Название кампании",
    "campaigns.startDate": "Дата начала",
    "campaigns.endDate": "Дата окончания",
    "campaigns.currency": "Валюта",
    "campaigns.status": "Статус",
    "campaigns.totalCustomers": "Всего клиентов",
    "campaigns.active": "Активна",
    "campaigns.archived": "Архивирована",

    // Customers
    "customers.title": "Клиенты",
    "customers.name": "Имя клиента",
    "customers.email": "Email",
    "customers.phone": "Телефон",
    "customers.totalPurchases": "Всего покупок",
    "customers.progress": "Прогресс",

    // Reports
    "reports.title": "Отчёты",
    "reports.overview": "Обзор",
    "reports.topCustomers": "Топ клиентов",
    "reports.giftLiability": "Обязательства по подаркам",
    "reports.claims": "Претензии",
    "reports.sales": "Продажи",
    "reports.qualified": "Квалифицировано",
    "reports.claims_count": "Претензии",
    "reports.purchaseAmount": "Сумма покупки",
    "reports.reachedTier": "Достигнутый уровень",
    "reports.activeClaims": "Активные претензии",

    // Integrations
    "integrations.title": "Интеграции",
    "integrations.newIntegration": "Новая интеграция",
    "integrations.provider": "Провайдер",
    "integrations.name": "Имя",
    "integrations.status": "Статус",
    "integrations.active": "Активна",
    "integrations.draft": "Черновик",
    "integrations.error": "Ошибка",

    // Import
    "import.title": "Импорт",
    "import.uploadFile": "Загрузить файл",
    "import.preview": "Предпросмотр",
    "import.confirm": "Подтвердить импорт",
    "import.rows": "Строки",
    "import.errors": "Ошибки",

    // Settings
    "settings.title": "Настройки",
    "settings.companySettings": "Настройки компании",
    "settings.userManagement": "Управление пользователями",
    "settings.notificationPreferences": "Предпочтения уведомлений",
  },
};

let currentLanguage: Language = "en";

export function getLanguage(): Language {
  return currentLanguage;
}

export function setLanguage(lang: Language): void {
  currentLanguage = lang;
  localStorage.setItem("language", lang);
}

export function loadLanguage(): void {
  const saved = localStorage.getItem("language");
  if (saved === "uz" || saved === "ru" || saved === "en") {
    currentLanguage = saved;
  }
}

export function t(key: string): string {
  const trans = translations[currentLanguage];
  return trans[key] || translations["en"][key] || key;
}

export function getLocale(): string {
  const localeMap: Record<Language, string> = {
    en: "en-US",
    uz: "uz-UZ",
    ru: "ru-RU",
  };
  return localeMap[currentLanguage];
}
