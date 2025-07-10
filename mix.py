"""
SQLite Database Viewer with AI Integration all
=========================================

This application provides a graphical interface for working with SQLite databases.
Features:
- Database selection and table management
- SQL query execution with AI support
- Voice input for queries
- History and favorites management
- Export to PDF
- User authentication and permissions

Main components:
- LoginDialog: User authentication
- SQLApp: Main application interface
"""

import sys
import sqlite3
import os
import speech_recognition as sr
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QLineEdit, QLabel, QDialog, QHBoxLayout, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QScrollArea, QGridLayout, QWidget,
    QGroupBox, QToolButton, QMenu, QCheckBox
)
from PyQt6.QtCore import Qt
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from g4f.client import Client
from reportlab.lib import colors

# Реєструємо шрифт Arial та Arial-Bold
pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Вхід")
        self.setGeometry(200, 200, 300, 120)
        layout = QVBoxLayout()

        # Поле для введення імені користувача
        self.user_label = QLabel("Користувач:")
        self.user_input = QLineEdit()
        layout.addWidget(self.user_label)
        layout.addWidget(self.user_input)

        # Поле для введення пароля
        self.pass_label = QLabel("Пароль:")
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pass_label)
        layout.addWidget(self.pass_input)

        # Кнопка для входу
        self.login_button = QPushButton("Увійти")
        self.login_button.clicked.connect(self.attempt_login)
        layout.addWidget(self.login_button)

        self.setLayout(layout)

    def attempt_login(self):
        username = self.user_input.text()
        password = self.pass_input.text()
        
        # Перевірка у базі даних
        try:
            # Використовуємо окрему базу даних для аутентифікації або вашу основну
            conn = sqlite3.connect("user_management.db")  # або self.db_path
            cursor = conn.cursor()
            
            # Створити таблицю, якщо вона не існує
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )''')
            
            # Для першого запуску: додати адміністратора
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                              ("admin", "admin123", "admin"))
                conn.commit()
            
            # Перевірити користувача
            cursor.execute("SELECT user_id, role FROM users WHERE username=? AND password=?", 
                          (username, password))
            user_data = cursor.fetchone()
            conn.close()
            
            if user_data:
                self.user_id = user_data[0]
                self.user_role = user_data[1]
                self.accept()
                return
                
        except Exception as e:
            print(f"Помилка при вході: {e}")
        
        # Якщо невдалий вхід
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Помилка входу", "Невірний логін або пароль")

class SQLApp(QWidget):
    def __init__(self, user_id=None, user_role=None):
        super().__init__()
        self.user_id = user_id
        self.user_role = user_role
        
        # === Window configuration ===
        self.setWindowTitle("SQL Viewer")
        self.setGeometry(100, 100, 1000, 700)
        
        # === Instance variables ===
        self.db_path = os.path.join(os.path.dirname(__file__), "project_management.db")
        self.pdf_export_path = os.path.expanduser("~/Documents")
        self.history = []
        self.favorites = []
        
        # === UI initialization ===
        # Create main horizontal splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create sidebar for history and favorites
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        # History section
        history_group = QGroupBox("Історія запитів")
        history_layout = QVBoxLayout()
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.load_from_history)
        history_layout.addWidget(self.history_list)
        history_group.setLayout(history_layout)
        sidebar_layout.addWidget(history_group)
        
        # Favorites section
        favorites_group = QGroupBox("Закріплені запити")
        favorites_layout = QVBoxLayout()
        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.load_from_favorites)
        favorites_layout.addWidget(self.favorites_list)
        favorites_group.setLayout(favorites_layout)
        sidebar_layout.addWidget(favorites_group)
        
        # Add sidebar to splitter
        main_splitter.addWidget(sidebar)
        
        # Main content area
        main_content = QWidget()
        layout = QVBoxLayout(main_content)
        
        # Database selection section
        db_layout = QHBoxLayout()
        self.db_label = QLabel("База даних:")
        db_layout.addWidget(self.db_label)
        
        self.db_path_label = QLabel(self.db_path)
        db_layout.addWidget(self.db_path_label, 1)  # Give this label more space
        
        self.db_select_button = QPushButton("Вибрати БД")
        self.db_select_button.clicked.connect(self.select_database)
        db_layout.addWidget(self.db_select_button)
        
        layout.addLayout(db_layout)

        # Tables access section with dropdown/grid for better handling of many tables
        self.tables_label = QLabel("Таблиці бази даних:")
        layout.addWidget(self.tables_label)
        
        # Create scrollable area for table buttons
        tables_scroll_area = QScrollArea()
        tables_scroll_area.setWidgetResizable(True)
        tables_container = QWidget()
        self.tables_grid = QGridLayout(tables_container)
        tables_scroll_area.setWidget(tables_container)
        tables_scroll_area.setMaximumHeight(120)  # Limit height
        layout.addWidget(tables_scroll_area)

        # Поле для введення запиту з голосовим введенням
        query_layout = QHBoxLayout()
        self.query_label = QLabel("Введіть ваш запит:")
        query_layout.addWidget(self.query_label)
        
        self.query_input = QLineEdit()
        query_layout.addWidget(self.query_input)
        
        # Додаємо кнопку голосового введення
        self.voice_button = QPushButton("🎤")
        self.voice_button.setToolTip("Голосове введення")
        self.voice_button.clicked.connect(self.voice_input)
        query_layout.addWidget(self.voice_button)
        
        # Add favorite button
        self.pin_button = QPushButton("📌")
        self.pin_button.setToolTip("Закріпити запит")
        self.pin_button.clicked.connect(self.add_to_favorites)
        query_layout.addWidget(self.pin_button)
        
        layout.addLayout(query_layout)

        # Основні кнопки для генерації та виконання - у новому окремому layout
        main_buttons_layout = QHBoxLayout()
        
        # Нова кнопка для використання AI (g4f) - тепер на першому місці
        self.ai_button = QPushButton("Генерувати ШІ")
        self.ai_button.clicked.connect(self.ai_query)
        self.ai_button.setMinimumHeight(40)  # Робимо кнопку більшою
        main_buttons_layout.addWidget(self.ai_button)
        
        # Кнопка виконання запиту - з новою назвою
        self.run_button = QPushButton("Виконати SQL запит")
        self.run_button.clicked.connect(self.execute_query)
        self.run_button.setMinimumHeight(40)  # Робимо кнопку більшою
        main_buttons_layout.addWidget(self.run_button)
        
        layout.addLayout(main_buttons_layout)

        # Додаткові кнопки для INSERT, DELETE, UPDATE
        btn_layout = QHBoxLayout()
        self.insert_button = QPushButton("Додати")
        self.insert_button.clicked.connect(self.insert_row)
        btn_layout.addWidget(self.insert_button)

        self.delete_button = QPushButton("Видалити")
        self.delete_button.clicked.connect(self.delete_row)
        btn_layout.addWidget(self.delete_button)

        self.update_button = QPushButton("Оновити")
        self.update_button.clicked.connect(self.update_row)
        btn_layout.addWidget(self.update_button)

        layout.addLayout(btn_layout)

        # Додаємо меню налаштувань та експорту
        settings_layout = QHBoxLayout()

  

        # Кнопка експорту в PDF
        self.export_pdf_button = QPushButton("📄 Експорт у PDF")
        self.export_pdf_button.setToolTip("Зберегти поточні результати у PDF файл")
        self.export_pdf_button.clicked.connect(self.export_to_pdf)
        settings_layout.addWidget(self.export_pdf_button)

        # Додаємо це меню налаштувань перед таблицею
        layout.addLayout(settings_layout)
        
        # Таблиця для виводу результатів
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Add content to splitter and set up the final layout
        main_splitter.addWidget(main_content)
        
        # Set the ratio between sidebar and main content (1:3)
        main_splitter.setSizes([200, 800])
        
        # Set up the main layout with the splitter
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(main_splitter)
        self.setLayout(main_layout)

        # Завантажуємо дані користувача
        self.load_user_preferences()
        self.load_user_favorites()
        self.load_user_history()
    
    # === USER DATA MANAGEMENT ===
    def load_user_preferences(self):
        """Завантаження налаштувань користувача"""
        if not self.user_id:
            return
            
        try:
            conn = sqlite3.connect("user_management.db")
            cursor = conn.cursor()
            
            # Створити таблицю, якщо вона не існує
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                last_db_path TEXT,
                pdf_export_path TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )''')
            
            cursor.execute("SELECT last_db_path, pdf_export_path FROM user_preferences WHERE user_id=?", 
                         (self.user_id,))
            prefs = cursor.fetchone()
            conn.close()
            
            if prefs:
                db_path, pdf_path = prefs
                if db_path and os.path.exists(db_path):
                    self.db_path = db_path
                    self.db_path_label.setText(self.db_path)
                    self.load_database_tables()
                    
                if pdf_path:
                    self.pdf_export_path = pdf_path
                else:
                    self.pdf_export_path = os.path.expanduser("~/Documents")
            else:
                # Створити запис для нового користувача
                conn = sqlite3.connect("user_management.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO user_preferences (user_id, last_db_path, pdf_export_path) VALUES (?, ?, ?)",
                             (self.user_id, self.db_path, os.path.expanduser("~/Documents")))
                conn.commit()
                conn.close()
                self.pdf_export_path = os.path.expanduser("~/Documents")
        except Exception as e:
            print(f"Помилка завантаження налаштувань: {e}")
    
    def load_user_favorites(self):
        """Завантаження закріплених запитів користувача"""
        if not self.user_id:
            return
            
        try:
            conn = sqlite3.connect("user_management.db")
            cursor = conn.cursor()
            
            # Створити таблицю, якщо вона не існує
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_favorites (
                favorite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT NOT NULL,
                query_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )''')
            
            cursor.execute("SELECT query, query_name FROM user_favorites WHERE user_id=? ORDER BY created_at DESC", 
                         (self.user_id,))
            favorites = cursor.fetchall()
            conn.close()
            
            # Очистити старі і завантажити нові
            self.favorites_list.clear()
            self.favorites = []
            
            for query, name in favorites:
                display_text = name if name else query[:50] + ("..." if len(query) > 50 else "")
                self.favorites.append(query)
                self.favorites_list.addItem(display_text)
                
        except Exception as e:
            print(f"Помилка завантаження закріплених запитів: {e}")
    
    def load_user_history(self):
        """Завантаження історії запитів користувача"""
        if not self.user_id:
            return
            
        try:
            conn = sqlite3.connect("user_management.db")
            cursor = conn.cursor()
            
            # Створити таблицю, якщо вона не існує
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )''')
            
            cursor.execute("SELECT query FROM user_history WHERE user_id=? ORDER BY executed_at DESC LIMIT 50", 
                         (self.user_id,))
            history_items = cursor.fetchall()
            conn.close()
            
            # Очистити старі і завантажити нові
            self.history_list.clear()
            self.history = []
            
            for item in history_items:
                query = item[0]
                self.history.append(query)
                self.history_list.addItem(query[:50] + ("..." if len(query) > 50 else ""))
                
        except Exception as e:
            print(f"Помилка завантаження історії запитів: {e}")

    def save_user_preferences(self):
        """Збереження налаштувань користувача"""
        if not self.user_id:
            return
            
        try:
            conn = sqlite3.connect("user_management.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE user_preferences SET last_db_path=?, pdf_export_path=? WHERE user_id=?",
                         (self.db_path, self.pdf_export_path, self.user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Помилка збереження налаштувань: {e}")

    # === DATABASE OPERATIONS ===
    def select_database(self):
        """Відкриває діалог вибору файлу для вибору бази даних"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Виберіть файл бази даних SQLite",
            os.path.dirname(self.db_path),  # Start in current DB directory
            "SQLite Files (*.db *.sqlite *.db3);;All Files (*)"
        )
        
        if file_path:
            self.db_path = file_path
            self.db_path_label.setText(self.db_path)
            
            # Test connection and update quick access buttons
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                print(f"Connected to {self.db_path}")
                print(f"Tables found: {tables}")
                conn.close()
                
                # Update quick access table buttons
                self.update_table_buttons(tables)
            except Exception as e:
                print(f"Error connecting to database: {e}")

    def update_table_buttons(self, tables):
        """Creates buttons for quick access to each table in a grid layout"""
        # Clear existing buttons first
        for i in reversed(range(self.tables_grid.count())): 
            self.tables_grid.itemAt(i).widget().setParent(None)
        
        # Add new buttons for each table in a grid (4 columns)
        MAX_COLS = 4
        row, col = 0, 0
        
        for table in tables:
            table_name = table[0]
            # Skip sqlite_sequence as it's a system table
            if table_name == "sqlite_sequence":
                continue
                
            btn = QPushButton(table_name)
            btn.clicked.connect(lambda checked, name=table_name: self.show_table(name))
            self.tables_grid.addWidget(btn, row, col)
            
            # Move to next column or row
            col += 1
            if col >= MAX_COLS:
                col = 0
                row += 1

    def show_table(self, table_name):
        """Shows all data from the selected table"""
        query = f"SELECT * FROM {table_name}"
        self.query_input.setText(query)
        self.execute_query()

    def execute_query(self):
        query = self.query_input.text()
        if not query:
            return
        
        # Перевірка прав доступу
        if not self.check_permissions(query):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Помилка прав доступу", 
                              "У вас немає прав на виконання цього запиту")
            return
        
        # Додавання запиту в історію
        if query not in self.history:
            self.history.append(query)
            self.history_list.addItem(query[:50] + ("..." if len(query) > 50 else ""))
            
            # Збереження у базу даних
            if self.user_id:
                try:
                    conn = sqlite3.connect("user_management.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO user_history (user_id, query) VALUES (?, ?)",
                                 (self.user_id, query))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Помилка збереження історії запитів: {e}")
        
        # Split the query into multiple statements
        queries = [q.strip() for q in query.split(';') if q.strip()]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        results = []
        last_columns = []
        try:
            # Execute each query separately
            for q in queries:
                cursor.execute(q)
                try:
                    rows = cursor.fetchall()
                    if cursor.description:  # If this query returns results
                        columns = [desc[0] for desc in cursor.description]
                        results.extend(rows)
                        last_columns = columns
                except sqlite3.Error:
                    # This might be an INSERT/UPDATE/DELETE that doesn't return results
                    pass
            
            # Commit all changes at once
            conn.commit()
        except Exception as e:
            results = []
            last_columns = []
            print(f"Помилка запиту: {e}")
        finally:
            conn.close()

        # Clear the table
        self.table.clear()
        
        # Display results if any
        if last_columns:
            self.table.setColumnCount(len(last_columns))
            self.table.setHorizontalHeaderLabels(last_columns)
        else:
            self.table.setColumnCount(0)
        
        # Display results
        self.table.setRowCount(len(results))
        # Ховаємо номери рядків 
        self.table.setVerticalHeaderLabels([""] * len(results))
        
        for i, row in enumerate(results):
            for j, value in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

    def check_permissions(self, query):
        """Перевірка прав доступу для виконання запиту"""
        if self.user_role == "admin":
            # Адміністратор має всі права
            return True
        
        if not self.user_id:
            # Якщо користувач не авторизований
            return False
        
        # Аналіз типу запиту
        query_lower = query.lower().strip()
        operation = None
        table_name = None
        
        if query_lower.startswith("select"):
            operation = "select"
        elif query_lower.startswith("insert"):
            operation = "insert"
        elif query_lower.startswith("update"):
            operation = "update"
        elif query_lower.startswith("delete"):
            operation = "delete"
        
        if operation:
            # Спрощений пошук назви таблиці
            # Це примітивний підхід, для складних запитів потрібен повноцінний SQL парсер
            if operation == "select":
                parts = query_lower.split("from")
                if len(parts) > 1:
                    table_part = parts[1].strip().split(" ")[0].split(";")[0]
                    table_name = table_part
            elif operation == "insert":
                parts = query_lower.split("into")
                if len(parts) > 1:
                    table_part = parts[1].strip().split(" ")[0].split("(")[0].split(";")[0]
                    table_name = table_part
            elif operation == "update":
                parts = query_lower.split("update")
                if len(parts) > 1:
                    table_part = parts[1].strip().split(" ")[0].split("set")[0].split(";")[0]
                    table_name = table_part
            elif operation == "delete":
                parts = query_lower.split("from")
                if len(parts) > 1:
                    table_part = parts[1].strip().split(" ")[0].split("where")[0].split(";")[0]
                    table_name = table_part
        
        if operation and table_name:
            # Перевірка прав доступу в базі
            try:
                conn = sqlite3.connect("user_management.db")
                cursor = conn.cursor()
                
                # Створити таблицю прав, якщо не існує
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    table_name TEXT NOT NULL,
                    can_select BOOLEAN DEFAULT 1,
                    can_insert BOOLEAN DEFAULT 0,
                    can_update BOOLEAN DEFAULT 0,
                    can_delete BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')
                
                # Перевірка прав
                permission_field = f"can_{operation}"
                cursor.execute(f"SELECT {permission_field} FROM user_permissions WHERE user_id=? AND table_name=?", 
                             (self.user_id, table_name))
                result = cursor.fetchone()
                
                if not result:
                    # Якщо немає правила, створити дефолтне
                    defaults = {"can_select": 1, "can_insert": 0, "can_update": 0, "can_delete": 0}
                    cursor.execute(
                        "INSERT INTO user_permissions (user_id, table_name, can_select, can_insert, can_update, can_delete) VALUES (?, ?, ?, ?, ?, ?)", 
                        (self.user_id, table_name, defaults["can_select"], defaults["can_insert"], defaults["can_update"], defaults["can_delete"])
                    )
                    conn.commit()
                    conn.close()
                    return defaults.get(permission_field, 0) == 1
                
                conn.close()
                return result[0] == 1
            except Exception as e:
                print(f"Помилка перевірки прав доступу: {e}")
        
        # За замовчуванням дозволяємо SELECT і забороняємо інші операції
        if operation == "select":
            return True
        return False

    # === AI FEATURES ===
    def voice_input(self):
        """Функція для голосового введення запиту."""
        recognizer = sr.Recognizer()
        self.query_input.setText("Listening...")
        
        try:
            with sr.Microphone() as source:
                self.query_input.setText("Говоріть...")
                # Налаштування для шумного середовища
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.listen(source, timeout=5)
                
            # Спроба розпізнати аудіо
            text = recognizer.recognize_google(audio, language='uk-UA')
            self.query_input.setText(text)
        except sr.UnknownValueError:
            self.query_input.setText("Не розпізнано, спробуйте ще раз")
        except sr.RequestError:
            self.query_input.setText("Помилка сервісу розпізнавання")
        except Exception as e:
            self.query_input.setText(f"Помилка: {str(e)}")

    def ai_query(self):
        # 1) Connect and gather table info
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        schemas = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            schemas[table_name] = columns
        conn.close()

        # 2) Generate query from g4f (same logic as console)
        query_text = self.query_input.text()
        if query_text.lower() == "exit":
            return
        sql_query = self.try_mysql(tables, schemas, query_text)
        print("Generated SQL:", sql_query)

        # 3) Execute and update table
        self.query_input.setText(sql_query)
        self.execute_query()

    def try_mysql(self, tables, schemas, query):
        """
        Викликає g4f для генерації SQL-запиту на основі опису схеми БД.
        """
        # Extract actual table names first
        actual_table_names = [table[0] for table in tables]
        print("Actual tables found:", actual_table_names)
        
        # Отримаємо доступні права користувача
        user_permissions = {}
        if self.user_id and self.user_role != "admin":
            try:
                conn = sqlite3.connect("user_management.db")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT table_name, can_select, can_insert, can_update, can_delete 
                    FROM user_permissions WHERE user_id=?
                """, (self.user_id,))
                for row in cursor.fetchall():
                    table, can_select, can_insert, can_update, can_delete = row
                    user_permissions[table] = {
                        "select": bool(can_select),
                        "insert": bool(can_insert),
                        "update": bool(can_update),
                        "delete": bool(can_delete)
                    }
                conn.close()
            except Exception as e:
                print(f"Помилка отримання прав доступу: {e}")
        
        # Додамо дефолтні права для таблиць, яких немає в налаштуваннях
        for table in actual_table_names:
            if table not in user_permissions:
                # За замовчуванням: лише select=True
                user_permissions[table] = {
                    "select": True,
                    "insert": self.user_role == "admin", 
                    "update": self.user_role == "admin", 
                    "delete": self.user_role == "admin"
                }
        
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"Ти — SQL-генератор. Виводь тільки працюючий SQL без пояснень, без маркування коду і зайвих атрибутів. "
                               f"НЕ ВИКОРИСТОВУЙ МАРКЕРИ ```sql або ``` в твоїй відповіді. "
                               f"ВАЖЛИВО: використовуй ЛИШЕ ті імена таблиць, які є в базі даних! "
                               f"Якщо потрібно додати кілька рядків, використовуй окремі INSERT запити з крапкою з комою в кінці. "
                               f"Враховуй права користувача на таблиці: {user_permissions}"
                },
                {
                    "role": "user",
                    "content": f"Ось структури таблиць: {schemas}. Доступні таблиці: {actual_table_names}. "
                               f"Згенеруй ЛИШЕ SQL! без лапок, без маркерів коду і додаткових пояснень, враховуючи мої права: {query}"
                }
            ],
            web_search=False
        )
        sql_code = response.choices[0].message.content
        
        # Очищення SQL коду від можливого форматування markdown
        generated_sql = sql_code.strip()
        generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
        
        print("Generated SQL:", generated_sql)
        
        # Validate that the query only references existing tables
        for table_name in actual_table_names:
            # Replace any translation with the actual table name if needed
            if "працівники" in generated_sql.lower() and "employees" in [t.lower() for t in actual_table_names]:
                generated_sql = generated_sql.replace("працівники", "employees")
        
        return generated_sql

    # === DATA MODIFICATION ===
    def insert_row(self):
        # Тут користувач може додавати свій INSERT-запит у self.query_input
        self.query_input.setText("INSERT INTO your_table (...) VALUES (...);")

    def delete_row(self):
        # Тут можна додавати DELETE-запит
        self.query_input.setText("DELETE FROM your_table WHERE id=...;")

    def update_row(self):
        # Тут можна додавати UPDATE-запит
        self.query_input.setText("UPDATE your_table SET column=value WHERE id=...;")

    # === HISTORY AND FAVORITES ===
    def load_from_history(self, item):
        """Load a query from history into the input field"""
        self.query_input.setText(item.text())
    
    def load_from_favorites(self, item):
        """Load a query from favorites into the input field"""
        self.query_input.setText(item.text())
    
    def add_to_favorites(self):
        """Add current query to favorites"""
        query = self.query_input.text()
        if not query or query in self.favorites:
            return
            
        # Запит назви для закладки
        from PyQt6.QtWidgets import QInputDialog
        query_name, ok = QInputDialog.getText(self, "Назва закладки", "Введіть назву для закріпленого запиту:")
        
        if not ok:
            return
            
        # Додавання до локального UI
        self.favorites.append(query)
        display_text = query_name if query_name else query[:50] + ("..." if len(query) > 50 else "")
        self.favorites_list.addItem(display_text)
        
        # Збереження у базу даних
        if self.user_id:
            try:
                conn = sqlite3.connect("user_management.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO user_favorites (user_id, query, query_name) VALUES (?, ?, ?)",
                             (self.user_id, query, query_name))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Помилка збереження закріпленого запиту: {e}")

    # === EXPORT AND SETTINGS ===
    def generate_pdf_filename(self, query):
        """Generate a PDF filename based on the query content using AI"""
        try:
            # Спрощена версія - просто повернути базову назву
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"sql_export_{timestamp}.pdf"
            
            # Спроба генерації через ШІ
            print("Генерую назву файлу за допомогою ШІ...")
            client = Client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Створи коротку описову назву файлу з суфіксом .pdf на основі SQL запиту. "
                                   "Назва має бути змістовна, українською мовою, без пробілів (використовуй _ замість пробілів). "
                                   "Наприклад, для запиту 'SELECT * FROM employees' поверни 'Список_працівників.pdf'"
                    },
                    {
                        "role": "user",
                        "content": f"Створи назву файлу для запиту: {query}"
                    }
                ],
                web_search=False
            )
            filename = response.choices[0].message.content.strip()
            print(f"ШІ згенерував назву: {filename}")
            
            # Ensure it has .pdf extension
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
                
            # Replace spaces with underscores
            filename = filename.replace(' ', '_')
            
            # Remove any invalid filename characters
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                filename = filename.replace(char, '_')
                
            print(f"Остаточна назва файлу: {filename}")
            return filename
        except Exception as e:
            print(f"Помилка при генерації назви файлу: {e}")
            # Return a fallback filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"sql_export_{timestamp}.pdf"

    def export_to_pdf(self):
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            from datetime import datetime
            
            # Get the query from the input field
            query = self.query_input.text()
            if not query:
                QMessageBox.warning(self, "PDF Export", "Немає даних для експорту!")
                return
            
            # Generate a meaningful filename based on query
            print("Запускаю генерацію імені файлу...")
            suggested_name = self.generate_pdf_filename(query)
            print(f"Запропонована назва файлу: {suggested_name}")
            
            # Ensure pdf_export_path exists
            if not self.pdf_export_path or not os.path.exists(self.pdf_export_path):
                self.pdf_export_path = os.path.expanduser("~/Documents")
                print(f"Встановлено шлях за замовчуванням: {self.pdf_export_path}")
            
            # Get full path for suggested file
            suggested_path = os.path.join(self.pdf_export_path, suggested_name)
            print(f"Пропонований повний шлях: {suggested_path}")
            
            # Open file dialog with the suggested name
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Зберегти як PDF",
                suggested_path,
                "PDF Files (*.pdf)"
            )
            
            if not filename:
                print("Користувач скасував операцію")
                return  # User canceled the operation
            
            print(f"Користувач вибрав шлях: {filename}")
                
            # Update stored path
            new_path = os.path.dirname(filename)
            print(f"Оновлюємо збережений шлях на: {new_path}")
            self.pdf_export_path = new_path
            self.save_user_preferences()
            
            # Create the PDF document with the generated filename
            print(f"Створюємо PDF документ: {filename}")
            doc = SimpleDocTemplate(filename)
            elements = []
            
            # Add title with query
            styles = getSampleStyleSheet()
            elements.append(Paragraph(f"SQL запит: {query}", styles['Heading2']))
            elements.append(Paragraph(f"Час створення: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", styles['Normal']))
            
            # Get column headers
            col_count = self.table.columnCount()
            if col_count == 0:
                QMessageBox.warning(self, "PDF Export", "Немає даних для експорту!")
                return
                
            print(f"Знайдено {col_count} стовпців")
            headers = [self.table.horizontalHeaderItem(i).text() for i in range(col_count)]
            
            # Create data list starting with headers
            data = [headers]
            
            # Add table data rows
            row_count = self.table.rowCount()
            print(f"Знайдено {row_count} рядків")
            
            for row in range(row_count):
                row_data = []
                for col in range(col_count):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            # Create the table
            pdf_table = Table(data)
            
            # Add table style
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
            ])
            pdf_table.setStyle(style)
            
            # Add the table to our document
            elements.append(pdf_table)
            
            # Build the document
            print("Створюємо PDF файл...")
            doc.build(elements)
            print(f"PDF файл створено успішно: {filename}")
            
            # Show feedback to the user
            QMessageBox.information(self, "PDF Export", f"Файл успішно збережено як:\n{filename}")
        except Exception as e:
            print(f"Помилка при експорті в PDF: {e}")
            QMessageBox.critical(self, "Помилка експорту", f"Не вдалося створити PDF файл.\nПомилка: {str(e)}")

    def set_pdf_path(self):
        """Дозволяє користувачу вибрати шлях для збереження PDF файлів"""
        try:
            directory = QFileDialog.getExistingDirectory(
                self, 
                "Виберіть папку для збереження PDF файлів",
                self.pdf_export_path or os.path.expanduser("~/Documents")
            )
            
            if (directory):
                self.pdf_export_path = directory
                self.save_user_preferences()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, 
                    "Шлях збереження PDF", 
                    f"PDF файли будуть зберігатися у:\n{directory}"
                )
        except Exception as e:
            print(f"Помилка при встановленні шляху для PDF: {e}")

    def toggle_row_numbers(self, state):
        """Показує або приховує номери рядків у таблиці"""
        # Оновлюємо відображення таблиці, якщо дані вже завантажені
        if self.table.rowCount() > 0:
            if state == Qt.CheckState.Checked:
                # Встановлюємо номери рядків
                self.table.setVerticalHeaderLabels([str(i+1) for i in range(self.table.rowCount())])
            else:
                # Встановлюємо пусті мітки
                self.table.setVerticalHeaderLabels([""] * self.table.rowCount())

def initialize_database():
    """Ініціалізувати базу даних з адміністратором"""
    try:
        # Перевірити наявність бази даних
        db_file = "user_management.db"
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Створити таблицю користувачів
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )''')
        
        # Перевірити наявність адміністратора
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        admin_count = cursor.fetchone()[0]
        
        # Якщо адміністраторів немає - створити стандартного
        if (admin_count == 0):
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                          ("admin", "admin123", "admin"))
            print("Створено стандартного адміністратора: логін = admin, пароль = admin123")
            
        conn.commit()
        conn.close()
        print("База даних ініціалізована успішно")
        return True
    except Exception as e:
        print(f"Помилка ініціалізації бази даних: {e}")
        return False

# Викликати функцію ініціалізації перед запуском програми
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Ініціалізувати базу даних перед відображенням діалогу входу
    initialize_database()
    
    # Відображаємо діалог входу
    login_dialog = LoginDialog()
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        # Якщо вхід успішний, відображаємо головне вікно
        window = SQLApp(login_dialog.user_id, login_dialog.user_role)
        window.show()
        sys.exit(app.exec())
