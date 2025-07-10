# SQLite Database Viewer with AI Integration

## Опис (Українською)

Ця програма надає зручний графічний інтерфейс для роботи з базами даних SQLite. Основні можливості:

- Вибір та перегляд бази даних
- Перегляд і керування таблицями
- Виконання SQL-запитів з підтримкою AI (g4f)
- Голосове введення запитів
- Історія та закріплення улюблених запитів
- Експорт результатів у PDF
- Аутентифікація користувачів та система прав доступу

### Запуск

1. Встановіть залежності:
   - Python 3.10+
   - PyQt6
   - speech_recognition
   - reportlab
   - g4f
2. Запустіть файл `mix.py`:
   ```bash
   python mix.py
   ```
3. При першому запуску створюється адміністратор (логін: `admin`, пароль: `admin123`).

### Примітки
- Для коректної роботи експорту в PDF потрібен шрифт Arial у системі Windows.
- Для голосового введення потрібен мікрофон.

---

## Description (English)

This application provides a convenient graphical interface for working with SQLite databases. Main features:

- Database selection and viewing
- Table management and browsing
- SQL query execution with AI (g4f) support
- Voice input for queries
- Query history and favorites
- Export results to PDF
- User authentication and permissions system

### How to Run

1. Install dependencies:
   - Python 3.10+
   - PyQt6
   - speech_recognition
   - reportlab
   - g4f
2. Run the `mix.py` file:
   ```bash
   python mix.py
   ```
3. On first launch, an admin user is created (login: `admin`, password: `admin123`).

### Notes
- PDF export requires Arial font installed (Windows).
- Voice input requires a microphone.
