from __future__ import annotations

import csv
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import vk_api
from dotenv import load_dotenv, set_key
from openpyxl import Workbook

from app.models import Community, CommunityCreate, CommentDraft, DraftStatus, PublishResult
from app.store import DB_PATH, store

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

POSTS_PER_COMMUNITY = 3


class DesktopApp:
    BG = "#f6f1e8"
    SURFACE = "#fffdfa"
    PANEL = "#efe5d8"
    INPUT = "#fffaf3"
    BORDER = "#d7c8b4"
    TEXT = "#2b2118"
    MUTED = "#6f6254"
    ACCENT = "#c78642"
    ACCENT_SOFT = "#ead6bc"
    SELECT = "#d9b88c"
    OK = "#2e7d32"
    ERR = "#c62828"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("VK Comment Assistant")
        self.root.geometry("1380x920")
        self.root.minsize(1100, 750)

        self.vk_session: vk_api.VkApi | None = None
        self.vk: vk_api.vk_api.VkApiMethod | None = None
        self.filter_status = tk.StringVar(value="all")
        import os
        self.posts_per_community = tk.IntVar(value=int(os.getenv("POSTS_PER_COMMUNITY", "3")))
        self.communities: list[Community] = []
        self.drafts_all: list[CommentDraft] = []
        self.drafts: list[CommentDraft] = []
        self.comm_check_vars: dict[str, tk.BooleanVar] = {}
        self._search_results: list[dict] = []
        self.compose_image_path: str | None = None
        self._monitor_results: list[dict] = []

        self._configure_style()
        self._bind_global_shortcuts()
        self._build_layout()
        self._try_restore_token()
        self.refresh_all()

    # ──────────────────────── style / shortcuts ────────────────────

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(bg=self.BG)
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT)
        style.configure("TLabelframe", background=self.SURFACE, foreground=self.TEXT, bordercolor=self.BORDER)
        style.configure("TLabelframe.Label", background=self.SURFACE, foreground=self.TEXT)
        style.configure("TButton", padding=8, background=self.ACCENT_SOFT, foreground=self.TEXT)
        style.map("TButton", background=[("active", self.PANEL)])
        style.configure("TEntry", fieldbackground=self.INPUT, foreground=self.TEXT)
        style.configure("TCombobox", fieldbackground=self.INPUT, background=self.INPUT, foreground=self.TEXT)
        style.configure(
            "Treeview", rowheight=28,
            fieldbackground=self.INPUT, background=self.INPUT,
            foreground=self.TEXT, bordercolor=self.BORDER,
        )
        style.configure("Treeview.Heading", background=self.PANEL, foreground=self.TEXT)
        style.map("Treeview", background=[("selected", self.SELECT)], foreground=[("selected", self.TEXT)])
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.PANEL, foreground=self.TEXT, padding=(12, 7))
        style.map("TNotebook.Tab", background=[("selected", self.SURFACE)])

    def _bind_global_shortcuts(self) -> None:
        """Fix Cmd+C/V/X/A/Z for all Text widgets on macOS."""
        for seq, event in [
            ("<Command-c>", "<<Copy>>"),
            ("<Command-x>", "<<Cut>>"),
            ("<Command-v>", "<<Paste>>"),
            ("<Command-z>", "<<Undo>>"),
        ]:
            self.root.bind_class("Text", seq,
                lambda e, ev=event: (e.widget.event_generate(ev), "break")[1])

        def select_all(e: tk.Event) -> str:
            e.widget.tag_add("sel", "1.0", "end")
            e.widget.mark_set("insert", "end")
            return "break"

        self.root.bind_class("Text", "<Command-a>", select_all)

        # Entry widgets
        for seq, event in [
            ("<Command-c>", "<<Copy>>"),
            ("<Command-x>", "<<Cut>>"),
            ("<Command-v>", "<<Paste>>"),
        ]:
            self.root.bind_class("Entry", seq,
                lambda e, ev=event: (e.widget.event_generate(ev), "break")[1])

        def select_all_entry(e: tk.Event) -> str:
            e.widget.select_range(0, "end")
            return "break"

        self.root.bind_class("Entry", "<Command-a>", select_all_entry)

    # ──────────────────────────── layout ──────────────────────────

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="VK Comment Assistant", font=("Helvetica", 20, "bold")).grid(row=0, column=0, sticky="w")
        self.auth_status_label = ttk.Label(header, text="Не подключен", font=("Helvetica", 11), foreground=self.ERR)
        self.auth_status_label.grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Button(header, text="Обновить", command=self.refresh_all).grid(row=0, column=2, sticky="e")

        stats_frame = ttk.LabelFrame(container, text="Сводка", padding=10)
        stats_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for i in range(4):
            stats_frame.columnconfigure(i, weight=1)
        self.stats_labels: dict[str, ttk.Label] = {}
        for col, key in enumerate(("communities", "pending", "published", "failed")):
            card = ttk.Frame(stats_frame, padding=8)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
            lbl = ttk.Label(card, text="0", font=("Helvetica", 18, "bold"))
            lbl.pack(anchor="w")
            caption = {"communities": "Сообществ", "pending": "На проверке",
                       "published": "Опубликовано", "failed": "Ошибок"}[key]
            ttk.Label(card, text=caption, foreground=self.MUTED).pack(anchor="w")
            self.stats_labels[key] = lbl

        notebook = ttk.Notebook(container)
        notebook.grid(row=2, column=0, sticky="nsew")

        self._build_auth_tab(notebook)
        self._build_communities_tab(notebook)
        self._build_compose_tab(notebook)
        self._build_drafts_tab(notebook)
        self._build_monitor_tab(notebook)
        self._build_settings_tab(notebook)

    # ─────────────────────────── Auth tab ─────────────────────────

    def _build_auth_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=20)
        notebook.add(tab, text="Авторизация")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

        form = ttk.LabelFrame(tab, text="Войти через логин и пароль ВКонтакте", padding=16)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Логин (телефон/email)").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
        self.login_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.login_var, width=32).grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Пароль").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
        self.password_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.password_var, show="•", width=32).grid(row=1, column=1, sticky="ew", pady=(0, 8))

        self.login_button = ttk.Button(form, text="Войти", command=self.do_login)
        self.login_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.login_status = ttk.Label(form, text="", wraplength=380)
        self.login_status.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        token_frame = ttk.LabelFrame(tab, text="Или вставить токен вручную", padding=16)
        token_frame.grid(row=0, column=1, sticky="nsew")
        token_frame.columnconfigure(0, weight=1)

        ttk.Label(token_frame, text="Access Token").pack(anchor="w", pady=(0, 4))
        self.token_var = tk.StringVar()
        ttk.Entry(token_frame, textvariable=self.token_var, show="•").pack(fill="x", pady=(0, 8))
        ttk.Button(token_frame, text="Применить токен", command=self.apply_token).pack(fill="x")

        note = (
            "Быстрый способ получить токен (Kate Mobile):\n\n"
            "Открой в браузере:\n"
            "https://oauth.vk.com/authorize?client_id=2685278"
            "&scope=wall,offline&redirect_uri=https://oauth.vk.com/blank.html"
            "&response_type=token&v=5.131\n\n"
            "Нажми «Разрешить» → скопируй access_token= из адресной строки."
        )
        ttk.Label(token_frame, text=note, wraplength=380, justify="left",
                  foreground=self.MUTED, font=("Helvetica", 10)).pack(anchor="w", pady=(16, 0))

    # ─────────────────────── Communities tab ──────────────────────

    def _build_communities_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Сообщества")
        tab.columnconfigure(0, weight=2)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        # Left — list
        left = ttk.LabelFrame(tab, text="Добавленные сообщества", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.comm_tree = ttk.Treeview(left, columns=("name", "screen_name", "vk_group_id"), show="headings")
        self.comm_tree.heading("name", text="Название")
        self.comm_tree.heading("screen_name", text="screen_name")
        self.comm_tree.heading("vk_group_id", text="ID группы")
        self.comm_tree.column("name", width=280)
        self.comm_tree.column("screen_name", width=180)
        self.comm_tree.column("vk_group_id", width=110, anchor="center")
        self.comm_tree.grid(row=0, column=0, sticky="nsew")
        self.comm_tree.bind("<Double-Button-1>", self._open_community_in_browser)

        ttk.Button(left, text="Удалить выбранное", command=self.delete_community).grid(
            row=1, column=0, sticky="ew", pady=(10, 0)
        )

        # Right — add methods notebook
        right_nb = ttk.Notebook(tab)
        right_nb.grid(row=0, column=1, sticky="nsew")

        self._build_comm_by_url_tab(right_nb)
        self._build_comm_search_tab(right_nb)
        self._build_comm_manual_tab(right_nb)

    def _build_comm_by_url_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=14)
        nb.add(tab, text="По ссылке")
        tab.columnconfigure(0, weight=1)

        ttk.Label(tab, text="Вставь ссылку на сообщество или screen_name:").pack(anchor="w", pady=(0, 4))
        self.url_var = tk.StringVar()
        ttk.Entry(tab, textvariable=self.url_var).pack(fill="x", pady=(0, 6))

        ttk.Label(tab, text="Примеры: vk.com/club123456  |  vk.com/apiclub  |  apiclub",
                  foreground=self.MUTED, font=("Helvetica", 9)).pack(anchor="w", pady=(0, 10))

        self.url_add_btn = ttk.Button(tab, text="Добавить сообщество", command=self.add_community_from_url)
        self.url_add_btn.pack(fill="x")

        self.url_status = ttk.Label(tab, text="", wraplength=300, justify="left")
        self.url_status.pack(anchor="w", pady=(10, 0))

    def _build_comm_search_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=14)
        nb.add(tab, text="Поиск")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x", pady=(0, 8))
        search_row.columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.search_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search_btn = ttk.Button(search_row, text="Найти", command=self.search_communities)
        self.search_btn.grid(row=0, column=1)
        self.search_var.trace_add("write", lambda *_: None)
        search_row.bind_all("<Return>", lambda e: self.search_communities() if self.search_var.get() else None)

        self.search_status = ttk.Label(tab, text="Требуется авторизация.", foreground=self.MUTED,
                                       font=("Helvetica", 9))
        self.search_status.pack(anchor="w", pady=(0, 6))

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill="both", expand=True, pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.search_listbox = tk.Listbox(
            list_frame, bg=self.INPUT, fg=self.TEXT,
            selectbackground=self.SELECT, relief="flat",
            font=("Helvetica", 11),
        )
        self.search_listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.search_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.search_listbox.configure(yscrollcommand=sb.set)
        self.search_listbox.bind("<Double-Button-1>", lambda _: self.add_from_search())

        ttk.Button(tab, text="Добавить выбранное", command=self.add_from_search).pack(fill="x")

    def _build_comm_manual_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=14)
        nb.add(tab, text="Вручную")
        tab.columnconfigure(1, weight=1)

        self.new_comm_group_id = tk.StringVar()
        self.new_comm_screen = tk.StringVar()
        self.new_comm_name = tk.StringVar()

        for row, (label, var) in enumerate([
            ("ID группы ВК", self.new_comm_group_id),
            ("screen_name", self.new_comm_screen),
            ("Название", self.new_comm_name),
        ]):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(0, 10))
            ttk.Entry(tab, textvariable=var).grid(row=row, column=1, sticky="ew", pady=(0, 10))

        ttk.Button(tab, text="Добавить", command=self.add_community_manual).grid(
            row=3, column=0, columnspan=2, sticky="ew"
        )

    # ─────────────────────────── Compose tab ──────────────────────

    def _build_compose_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Новый комментарий")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(tab, text="Текст комментария", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.compose_text = tk.Text(
            left, wrap="word", bg=self.INPUT, fg=self.TEXT,
            insertbackground=self.TEXT, relief="flat", padx=12, pady=12,
            font=("Helvetica", 13), undo=True,
        )
        self.compose_text.grid(row=0, column=0, sticky="nsew")
        self.compose_text.bind("<KeyRelease>", self._update_char_count)

        char_frame = ttk.Frame(left)
        char_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.char_count_label = ttk.Label(char_frame, text="0 / 4000", foreground=self.MUTED)
        self.char_count_label.pack(side="right")

        img_frame = ttk.Frame(left)
        img_frame.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(img_frame, text="Прикрепить фото", command=self._pick_image).pack(side="left")
        ttk.Button(img_frame, text="X", command=self._clear_image, width=3).pack(side="left", padx=(4, 0))
        self.image_label = ttk.Label(img_frame, text="Фото не выбрано", foreground=self.MUTED)
        self.image_label.pack(side="left", padx=(10, 0))

        right = ttk.LabelFrame(tab, text="Целевые сообщества", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.comm_checkboxes_frame = ttk.Frame(right)
        self.comm_checkboxes_frame.grid(row=0, column=0, sticky="nsew")

        self.submit_draft_button = ttk.Button(
            right, text="Отправить на модерацию", command=self.submit_draft
        )
        self.submit_draft_button.grid(row=1, column=0, sticky="ew", pady=(12, 0))

    # ─────────────────────────── Drafts tab ───────────────────────

    def _build_drafts_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Черновики")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        tab.rowconfigure(2, weight=1)

        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Статус").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Combobox(
            controls, textvariable=self.filter_status,
            values=("all", "pending_review", "published", "publish_failed", "rejected"),
            state="readonly", width=20,
        ).grid(row=0, column=1, sticky="w")
        ttk.Button(controls, text="Экспорт CSV", command=self.export_csv).grid(row=0, column=2, padx=(10, 0))
        ttk.Button(controls, text="Экспорт Excel", command=self.export_excel).grid(row=0, column=3, padx=(10, 0))
        self.filter_status.trace_add("write", lambda *_: self.refresh_drafts())

        self.drafts_tree = ttk.Treeview(tab, columns=("status", "communities", "created"), show="headings")
        self.drafts_tree.grid(row=1, column=0, sticky="nsew")
        for name, title, width, anchor in (
            ("status", "Статус", 160, "center"),
            ("communities", "Сообщества", 500, "w"),
            ("created", "Создан", 160, "center"),
        ):
            self.drafts_tree.heading(name, text=title)
            self.drafts_tree.column(name, width=width, anchor=anchor)
        self.drafts_tree.bind("<<TreeviewSelect>>", lambda _: self.show_draft_details())

        bottom = ttk.Frame(tab)
        bottom.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)

        self.draft_details = self._make_readonly_text(bottom, height=13)
        self.draft_details.grid(row=0, column=0, columnspan=4, sticky="nsew")

        ttk.Label(bottom, text="Заметка").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.moderation_note = self._make_editor_text(bottom, height=2)
        self.moderation_note.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self.approve_button = ttk.Button(
            bottom, text="Одобрить и опубликовать", command=self.approve_draft,
        )
        self.approve_button.grid(row=2, column=1, sticky="ew", padx=(10, 10), pady=(6, 0))
        ttk.Button(bottom, text="Отклонить", command=self.reject_draft).grid(
            row=2, column=2, sticky="ew", pady=(6, 0)
        )
        self.publish_progress = ttk.Label(bottom, text="", foreground=self.MUTED)
        self.publish_progress.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # ──────────────────────────── Auth ────────────────────────────

    def _try_restore_token(self) -> None:
        import os
        token = os.getenv("VK_ACCESS_TOKEN", "").strip()
        if token:
            try:
                session = vk_api.VkApi(token=token)
                self.vk_session = session
                self.vk = session.get_api()
                self._set_auth_ok("Токен из .env активен")
            except Exception:
                pass

    def do_login(self) -> None:
        login = self.login_var.get().strip()
        password = self.password_var.get()
        if not login or not password:
            messagebox.showerror("Ошибка", "Заполни логин и пароль.")
            return
        self.login_button.configure(state="disabled")
        self.login_status.configure(text="Подключаюсь...", foreground=self.MUTED)
        threading.Thread(target=self._do_login_thread, args=(login, password), daemon=True).start()

    def _do_login_thread(self, login: str, password: str) -> None:
        try:
            session = vk_api.VkApi(
                login, password,
                auth_handler=self._two_factor_handler,
                captcha_handler=self._captcha_handler,
                scope="wall,photos,messages,offline",
            )
            session.auth(token_only=True)
            self.vk_session = session
            self.vk = session.get_api()
            token = session.token["access_token"]
            self._persist_token(token)
            me = self.vk.users.get()[0]
            name = f"{me['first_name']} {me['last_name']}"
            self.root.after(0, lambda: self._set_auth_ok(f"Подключен как {name}"))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._set_auth_error(str(e)))

    def apply_token(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Ошибка", "Вставь токен.")
            return
        try:
            session = vk_api.VkApi(token=token)
            self.vk_session = session
            self.vk = session.get_api()
            self._persist_token(token)
            me = self.vk.users.get()[0]
            name = f"{me['first_name']} {me['last_name']}"
            self._set_auth_ok(f"Подключен как {name}")
        except Exception as exc:
            messagebox.showerror("Ошибка токена", str(exc))

    def _set_auth_ok(self, text: str) -> None:
        self.auth_status_label.configure(text=text, foreground=self.OK)
        self.login_button.configure(state="normal")
        self.login_status.configure(text=text, foreground=self.OK)

    def _set_auth_error(self, text: str) -> None:
        self.auth_status_label.configure(text="Ошибка авторизации", foreground=self.ERR)
        self.login_button.configure(state="normal")
        self.login_status.configure(text=text, foreground=self.ERR)

    def _two_factor_handler(self) -> tuple[str, bool]:
        code = simpledialog.askstring(
            "Двухфакторная аутентификация", "Введи код из SMS или приложения:", parent=self.root,
        )
        return (code or "", True)

    def _captcha_handler(self, captcha: vk_api.Captcha) -> vk_api.Captcha:
        import webbrowser
        webbrowser.open(captcha.get_url())
        code = simpledialog.askstring("Капча", "Капча открыта в браузере. Введи текст:", parent=self.root)
        return captcha.try_again(code or "")

    def _persist_token(self, token: str) -> None:
        import os
        os.environ["VK_ACCESS_TOKEN"] = token
        ENV_FILE.touch()
        set_key(str(ENV_FILE), "VK_ACCESS_TOKEN", token)

    # ────────────────────── Community add methods ─────────────────

    def add_community_from_url(self) -> None:
        if not self.vk:
            self.url_status.configure(text="Сначала авторизуйся на вкладке Авторизация.", foreground=self.ERR)
            return
        raw = self.url_var.get().strip()
        if not raw:
            self.url_status.configure(text="Введи ссылку или screen_name.", foreground=self.ERR)
            return

        # Extract screen_name or numeric id from URL
        screen = re.sub(r"https?://(www\.)?vk\.com/", "", raw).strip("/")
        # Remove club/public prefix to get numeric id
        numeric_match = re.match(r"^(?:club|public|group)?(\d+)$", screen)
        if numeric_match:
            lookup = numeric_match.group(1)
        else:
            lookup = screen

        self.url_add_btn.configure(state="disabled")
        self.url_status.configure(text="Загружаю...", foreground=self.MUTED)
        threading.Thread(target=self._resolve_url_thread, args=(lookup,), daemon=True).start()

    def _resolve_url_thread(self, lookup: str) -> None:
        try:
            result = self.vk.groups.getById(group_ids=lookup, fields="")
            group = result[0]
            group_id = group["id"]
            screen_name = group.get("screen_name", str(group_id))
            name = group["name"]
            store.create_community(CommunityCreate(
                vk_group_id=group_id, screen_name=screen_name, name=name,
            ))
            self.root.after(0, lambda: self._on_url_add_done(name))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._on_url_add_error(str(e)))

    def _on_url_add_done(self, name: str) -> None:
        self.url_add_btn.configure(state="normal")
        self.url_var.set("")
        self.url_status.configure(text=f"Добавлено: {name}", foreground=self.OK)
        self.refresh_all()

    def _on_url_add_error(self, err: str) -> None:
        self.url_add_btn.configure(state="normal")
        self.url_status.configure(text=f"Ошибка: {err}", foreground=self.ERR)

    def search_communities(self) -> None:
        if not self.vk:
            self.search_status.configure(text="Сначала авторизуйся.", foreground=self.ERR)
            return
        query = self.search_var.get().strip()
        if not query:
            return
        self.search_btn.configure(state="disabled")
        self.search_status.configure(text="Поиск...", foreground=self.MUTED)
        self.search_listbox.delete(0, "end")
        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _search_thread(self, query: str) -> None:
        try:
            resp = self.vk.groups.search(q=query, count=20, type="group")
            items = resp.get("items", [])
            self.root.after(0, lambda: self._on_search_done(items))
        except Exception as exc:
            self.root.after(0, lambda e=exc: self._on_search_error(str(e)))

    def _on_search_done(self, items: list[dict]) -> None:
        self.search_btn.configure(state="normal")
        self._search_results = items
        self.search_listbox.delete(0, "end")
        for g in items:
            self.search_listbox.insert("end", f"{g['name']}  (vk.com/{g.get('screen_name', g['id'])})")
        self.search_status.configure(
            text=f"Найдено: {len(items)}. Двойной клик или кнопка — добавить.", foreground=self.MUTED
        )

    def _on_search_error(self, err: str) -> None:
        self.search_btn.configure(state="normal")
        self.search_status.configure(text=f"Ошибка: {err}", foreground=self.ERR)

    def add_from_search(self) -> None:
        sel = self.search_listbox.curselection()
        if not sel:
            messagebox.showwarning("Нет выбора", "Выбери сообщество из списка.")
            return
        group = self._search_results[sel[0]]
        store.create_community(CommunityCreate(
            vk_group_id=group["id"],
            screen_name=group.get("screen_name", str(group["id"])),
            name=group["name"],
        ))
        self.refresh_all()
        self.search_status.configure(text=f"Добавлено: {group['name']}", foreground=self.OK)

    def add_community_manual(self) -> None:
        raw_id = self.new_comm_group_id.get().strip()
        screen = self.new_comm_screen.get().strip()
        name = self.new_comm_name.get().strip()
        if not raw_id or not screen or not name:
            messagebox.showerror("Ошибка", "Заполни все поля.")
            return
        try:
            group_id = int(raw_id)
        except ValueError:
            messagebox.showerror("Ошибка", "ID группы должен быть числом.")
            return
        store.create_community(CommunityCreate(vk_group_id=group_id, screen_name=screen, name=name))
        self.new_comm_group_id.set("")
        self.new_comm_screen.set("")
        self.new_comm_name.set("")
        self.refresh_all()

    # ─────────────────────────── Monitor tab ──────────────────────

    def _build_monitor_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Мониторинг")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        # Keywords config
        kw_frame = ttk.LabelFrame(tab, text="Ключевые фразы", padding=10)
        kw_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        kw_frame.columnconfigure(1, weight=1)

        ttk.Label(kw_frame, text="Фразы (через запятую):").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.keywords_var = tk.StringVar()
        ttk.Entry(kw_frame, textvariable=self.keywords_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ttk.Label(kw_frame, text="Постов на сообщество:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.monitor_posts_count = tk.IntVar(value=10)
        tk.Spinbox(
            kw_frame, from_=1, to=100, textvariable=self.monitor_posts_count,
            width=6, bg=self.INPUT, fg=self.TEXT, relief="flat", font=("Helvetica", 13),
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))

        # Scan button row
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.scan_btn = ttk.Button(btn_frame, text="Сканировать сообщества", command=self.scan_keywords)
        self.scan_btn.pack(side="left")
        self.scan_status = ttk.Label(btn_frame, text="", foreground=self.MUTED)
        self.scan_status.pack(side="left", padx=(12, 0))

        # Results tree
        result_frame = ttk.LabelFrame(tab, text="Найденные результаты", padding=8)
        result_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)

        self.monitor_tree = ttk.Treeview(
            result_frame,
            columns=("community", "author", "text", "type"),
            show="headings",
        )
        for col, title, width in (
            ("community", "Сообщество", 180),
            ("author", "Автор", 160),
            ("text", "Текст", 450),
            ("type", "Тип", 100),
        ):
            self.monitor_tree.heading(col, text=title)
            self.monitor_tree.column(col, width=width, anchor="w" if col != "type" else "center")
        self.monitor_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(result_frame, orient="vertical", command=self.monitor_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.monitor_tree.configure(yscrollcommand=sb.set)

        # DM compose panel
        dm_frame = ttk.LabelFrame(tab, text="Личное сообщение (ЛС)", padding=10)
        dm_frame.grid(row=3, column=0, sticky="ew")
        dm_frame.columnconfigure(0, weight=1)

        self.dm_text = self._make_editor_text(dm_frame, height=4)
        self.dm_text.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        ttk.Button(dm_frame, text="Написать выбранному", command=self._send_dm_selected).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Button(dm_frame, text="Написать всем в списке", command=self._send_dm_all).grid(
            row=1, column=1, sticky="w", padx=(8, 0)
        )
        self.dm_status = ttk.Label(dm_frame, text="", foreground=self.MUTED, wraplength=700)
        self.dm_status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # ─────────────────────── Monitor actions ──────────────────────

    def scan_keywords(self) -> None:
        if not self.vk:
            self.scan_status.configure(text="Сначала авторизуйся.", foreground=self.ERR)
            return
        keywords_raw = self.keywords_var.get().strip()
        if not keywords_raw:
            self.scan_status.configure(text="Введи ключевые фразы.", foreground=self.ERR)
            return
        communities = store.list_communities()
        if not communities:
            self.scan_status.configure(text="Нет добавленных сообществ.", foreground=self.ERR)
            return
        keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
        for item in self.monitor_tree.get_children():
            self.monitor_tree.delete(item)
        self._monitor_results = []
        self.scan_btn.configure(state="disabled")
        self.scan_status.configure(text="Сканирую...", foreground=self.MUTED)
        threading.Thread(
            target=self._scan_thread,
            args=(communities, keywords, self.monitor_posts_count.get()),
            daemon=True,
        ).start()

    def _scan_thread(self, communities: list, keywords: list[str], posts_count: int) -> None:
        results: list[dict] = []
        total = len(communities)
        for idx, community in enumerate(communities, 1):
            self.root.after(
                0,
                lambda n=community.name, i=idx:
                    self.scan_status.configure(text=f"Сканирую {i}/{total}: {n}...", foreground=self.MUTED),
            )
            owner_id = -community.vk_group_id
            try:
                posts_resp = self.vk.wall.get(owner_id=owner_id, count=posts_count, filter="all")
                posts = posts_resp.get("items", [])
            except Exception:
                continue

            for post in posts:
                post_id = post["id"]
                from_id = post.get("from_id", 0)
                post_text = post.get("text", "")
                if from_id > 0 and any(kw in post_text.lower() for kw in keywords):
                    results.append({
                        "community": community.name,
                        "author_id": from_id,
                        "author_name": "",
                        "text": post_text[:200],
                        "type": "пост",
                    })
                # scan comments
                try:
                    comm_resp = self.vk.wall.getComments(owner_id=owner_id, post_id=post_id, count=100)
                    for comment in comm_resp.get("items", []):
                        c_from = comment.get("from_id", 0)
                        c_text = comment.get("text", "")
                        if c_from > 0 and any(kw in c_text.lower() for kw in keywords):
                            results.append({
                                "community": community.name,
                                "author_id": c_from,
                                "author_name": "",
                                "text": c_text[:200],
                                "type": "комментарий",
                            })
                except Exception:
                    pass

        # Resolve author names in batch
        if results:
            ids = list({r["author_id"] for r in results})
            try:
                users = self.vk.users.get(user_ids=",".join(str(i) for i in ids[:1000]))
                name_map = {u["id"]: f"{u['first_name']} {u['last_name']}" for u in users}
                for r in results:
                    r["author_name"] = name_map.get(r["author_id"], str(r["author_id"]))
            except Exception:
                for r in results:
                    r["author_name"] = str(r["author_id"])

        self.root.after(0, lambda: self._on_scan_done(results))

    def _on_scan_done(self, results: list[dict]) -> None:
        self.scan_btn.configure(state="normal")
        self._monitor_results = results
        for i, r in enumerate(results):
            self.monitor_tree.insert("", "end", iid=str(i),
                                    values=(r["community"], r["author_name"], r["text"], r["type"]))
        color = self.OK if results else self.MUTED
        self.scan_status.configure(text=f"Найдено: {len(results)} результатов.", foreground=color)

    def _send_dm_selected(self) -> None:
        selected = self.monitor_tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выбери строку из результатов.")
            return
        result = self._monitor_results[int(selected[0])]
        self._send_dm_to([result])

    def _send_dm_all(self) -> None:
        if not self._monitor_results:
            messagebox.showwarning("Нет данных", "Сначала выполни сканирование.")
            return
        seen: set[int] = set()
        unique = []
        for r in self._monitor_results:
            if r["author_id"] not in seen:
                seen.add(r["author_id"])
                unique.append(r)
        if not messagebox.askyesno("Подтверждение", f"Отправить ЛС {len(unique)} уникальным пользователям?"):
            return
        self._send_dm_to(unique)

    def _send_dm_to(self, targets: list[dict]) -> None:
        if not self.vk:
            messagebox.showerror("Не авторизован", "Сначала войди в аккаунт ВК.")
            return
        message = self.dm_text.get("1.0", "end").strip()
        if not message:
            messagebox.showwarning("Нет текста", "Напиши текст сообщения в поле ниже.")
            return
        self.dm_status.configure(text="Отправляю...", foreground=self.MUTED)
        threading.Thread(target=self._dm_thread, args=(targets, message), daemon=True).start()

    def _dm_thread(self, targets: list[dict], message: str) -> None:
        import random
        ok = 0
        errors: list[str] = []
        for target in targets:
            try:
                self.vk.messages.send(
                    user_id=target["author_id"],
                    message=message,
                    random_id=random.randint(1, 2 ** 31),
                )
                ok += 1
            except Exception as exc:
                errors.append(f"{target['author_name']}: {exc}")

        def update() -> None:
            if errors:
                preview = errors[0][:100]
                self.dm_status.configure(
                    text=f"Отправлено: {ok}, ошибок: {len(errors)}. Первая: {preview}",
                    foreground=self.ERR if ok == 0 else self.MUTED,
                )
            else:
                self.dm_status.configure(text=f"Успешно отправлено: {ok}", foreground=self.OK)

        self.root.after(0, update)

    # ─────────────────────────── Settings tab ─────────────────────

    def _build_settings_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=20)
        notebook.add(tab, text="Настройки")
        tab.columnconfigure(1, weight=1)

        section = ttk.LabelFrame(tab, text="Публикация", padding=16)
        section.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="Количество последних постов для комментирования").grid(
            row=0, column=0, sticky="w", padx=(0, 16), pady=(0, 4)
        )
        spin = tk.Spinbox(
            section,
            from_=1, to=50,
            textvariable=self.posts_per_community,
            width=6,
            bg=self.INPUT, fg=self.TEXT,
            relief="flat",
            font=("Helvetica", 13),
        )
        spin.grid(row=0, column=1, sticky="w", pady=(0, 4))
        ttk.Label(
            section,
            text="Например: 3 → комментарий появится под тремя последними постами каждого выбранного сообщества.",
            foreground=self.MUTED,
            font=("Helvetica", 10),
            wraplength=500,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        ttk.Button(section, text="Сохранить", command=self._save_settings).grid(
            row=2, column=0, sticky="w"
        )
        self.settings_status = ttk.Label(section, text="", foreground=self.OK)
        self.settings_status.grid(row=2, column=1, sticky="w", padx=(12, 0))

    def _save_settings(self) -> None:
        import os
        val = self.posts_per_community.get()
        if val < 1:
            self.posts_per_community.set(1)
            val = 1
        os.environ["POSTS_PER_COMMUNITY"] = str(val)
        ENV_FILE.touch()
        set_key(str(ENV_FILE), "POSTS_PER_COMMUNITY", str(val))
        self.settings_status.configure(text=f"Сохранено: {val} постов")
        self.root.after(2500, lambda: self.settings_status.configure(text=""))

    def _open_community_in_browser(self, _event=None) -> None:
        import webbrowser
        selected = self.comm_tree.selection()
        if not selected:
            return
        community = store.get_community(selected[0])
        if community:
            webbrowser.open(f"https://vk.com/{community.screen_name}")

    def delete_community(self) -> None:
        selected = self.comm_tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выбери сообщество.")
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранное сообщество?"):
            store.delete_community(selected[0])
            self.refresh_all()

    # ──────────────────────────── Compose ─────────────────────────

    def submit_draft(self) -> None:
        text = self.compose_text.get("1.0", "end").strip()
        community_ids = [cid for cid, var in self.comm_check_vars.items() if var.get()]
        if not text:
            messagebox.showwarning("Нет текста", "Напиши текст комментария.")
            return
        if not community_ids:
            messagebox.showwarning("Нет сообществ", "Выбери хотя бы одно сообщество.")
            return
        if self.compose_image_path and not self.vk:
            messagebox.showerror("Ошибка", "Для загрузки фото нужна авторизация.")
            return
        image_path = self.compose_image_path
        self.submit_draft_button.configure(state="disabled", text="Загружаю...")
        threading.Thread(
            target=self._submit_draft_thread,
            args=(text, community_ids, image_path),
            daemon=True,
        ).start()

    def _submit_draft_thread(self, text: str, community_ids: list[str], image_path: str | None) -> None:
        image_attachment = None
        if image_path:
            try:
                upload = vk_api.VkUpload(self.vk_session)
                photos = upload.photo_wall(image_path)
                photo = photos[0]
                image_attachment = f"photo{photo['owner_id']}_{photo['id']}"
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_image_upload_error(str(e)))
                return
        store.create_draft(text, community_ids, image_attachment=image_attachment)
        self.root.after(0, self._on_draft_submitted)

    def _on_image_upload_error(self, err: str) -> None:
        self.submit_draft_button.configure(state="normal", text="Отправить на модерацию")
        messagebox.showerror("Ошибка загрузки фото", err)

    def _on_draft_submitted(self) -> None:
        self.submit_draft_button.configure(state="normal", text="Отправить на модерацию")
        self.compose_text.delete("1.0", "end")
        self._clear_image()
        for var in self.comm_check_vars.values():
            var.set(False)
        self.refresh_all()
        messagebox.showinfo("Готово", "Черновик добавлен в очередь.")

    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Выбери фото",
            filetypes=(("Изображения", "*.jpg *.jpeg *.png *.gif *.bmp"), ("Все файлы", "*.*")),
        )
        if path:
            self.compose_image_path = path
            self.image_label.configure(text=Path(path).name, foreground=self.OK)

    def _clear_image(self) -> None:
        self.compose_image_path = None
        self.image_label.configure(text="Фото не выбрано", foreground=self.MUTED)

    # ──────────────────────────── Drafts ──────────────────────────

    def approve_draft(self) -> None:
        if not self.vk:
            messagebox.showerror("Не авторизован", "Сначала войди в аккаунт ВК на вкладке Авторизация.")
            return
        selected = self.drafts_tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выбери черновик.")
            return
        draft = store.get_draft(selected[0])
        if not draft or draft.status != DraftStatus.pending_review:
            messagebox.showerror("Ошибка", "Черновик не найден или уже обработан.")
            return
        note = self.moderation_note.get("1.0", "end").strip() or None
        self.approve_button.configure(state="disabled")
        self.publish_progress.configure(text="Публикую...", foreground=self.MUTED)
        threading.Thread(target=self._publish_thread, args=(draft, note), daemon=True).start()

    def _publish_thread(self, draft: CommentDraft, note: str | None) -> None:
        communities = [c for c in (store.get_community(cid) for cid in draft.community_ids) if c]
        results: list[PublishResult] = []

        for community in communities:
            owner_id = -community.vk_group_id
            try:
                posts = self.vk.wall.get(owner_id=owner_id, count=self.posts_per_community.get(), filter="all")
                items = posts.get("items", [])
            except Exception as exc:
                results.append(PublishResult(
                    vk_owner_id=owner_id, vk_post_id=0,
                    error=f"Ошибка постов [{community.name}]: {exc}",
                ))
                continue
            for post in items:
                post_id = post["id"]
                try:
                    kwargs: dict = {"owner_id": owner_id, "post_id": post_id, "message": draft.text}
                    if draft.image_attachment:
                        kwargs["attachments"] = draft.image_attachment
                    resp = self.vk.wall.createComment(**kwargs)
                    results.append(PublishResult(
                        vk_owner_id=owner_id, vk_post_id=post_id,
                        comment_id=resp["comment_id"],
                    ))
                except Exception as exc:
                    results.append(PublishResult(
                        vk_owner_id=owner_id, vk_post_id=post_id, error=str(exc),
                    ))

        has_success = any(r.comment_id is not None for r in results)
        all_failed = all(r.error for r in results) if results else True
        new_status = DraftStatus.publish_failed if (not results or all_failed) else DraftStatus.published
        updated = draft.model_copy(update={"status": new_status, "moderation_note": note, "publish_results": results})
        store.save_draft(updated)
        self.root.after(0, lambda: self._on_publish_done(updated))

    def _on_publish_done(self, draft: CommentDraft) -> None:
        self.approve_button.configure(state="normal")
        ok = sum(1 for r in draft.publish_results if r.comment_id)
        err = sum(1 for r in draft.publish_results if r.error)
        if draft.status == DraftStatus.published:
            self.publish_progress.configure(text=f"Опубликовано: {ok}, ошибок: {err}", foreground=self.OK)
        else:
            self.publish_progress.configure(text=f"Все попытки неудачны. Ошибок: {err}", foreground=self.ERR)
        self.refresh_drafts()
        self.refresh_stats()
        self.drafts_tree.selection_set(draft.id)
        self.show_draft_details()

    def reject_draft(self) -> None:
        selected = self.drafts_tree.selection()
        if not selected:
            messagebox.showwarning("Нет выбора", "Выбери черновик.")
            return
        draft = store.get_draft(selected[0])
        if not draft:
            return
        note = self.moderation_note.get("1.0", "end").strip() or None
        updated = draft.model_copy(update={"status": DraftStatus.rejected, "moderation_note": note})
        store.save_draft(updated)
        self.refresh_drafts()
        self.refresh_stats()

    def show_draft_details(self) -> None:
        selected = self.drafts_tree.selection()
        if not selected:
            self._set_text(self.draft_details, "Выбери черновик.")
            return
        draft = store.get_draft(selected[0])
        if not draft:
            return
        comm_map = {c.id: c.name for c in self.communities}
        comm_names = ", ".join(comm_map.get(cid, cid) for cid in draft.community_ids)
        lines = [
            f"ID: {draft.id}",
            f"Статус: {draft.status.value}",
            f"Сообщества: {comm_names}",
            f"Создан: {self._fmt_dt(draft.created_at)}",
            f"Заметка: {draft.moderation_note or '—'}",
            "",
            "Текст:",
            draft.text,
        ]
        if draft.publish_results:
            lines += ["", "Результаты публикации:"]
            for r in draft.publish_results:
                if r.comment_id:
                    lines.append(f"  ✓ Пост {r.vk_post_id} → комментарий #{r.comment_id}")
                else:
                    lines.append(f"  ✗ Пост {r.vk_post_id}: {r.error}")
        self._set_text(self.draft_details, "\n".join(lines))
        self._set_editor_text(self.moderation_note, draft.moderation_note or "")

    # ──────────────────────────── Refresh ─────────────────────────

    def refresh_all(self) -> None:
        self.communities = store.list_communities()
        self.drafts_all = store.list_drafts()
        self._refresh_communities_tree()
        self._refresh_comm_checkboxes()
        self.refresh_drafts()
        self.refresh_stats()

    def refresh_stats(self) -> None:
        pending = sum(1 for d in self.drafts_all if d.status == DraftStatus.pending_review)
        published = sum(1 for d in self.drafts_all if d.status == DraftStatus.published)
        failed = sum(1 for d in self.drafts_all if d.status == DraftStatus.publish_failed)
        self.stats_labels["communities"].configure(text=str(len(self.communities)))
        self.stats_labels["pending"].configure(text=str(pending))
        self.stats_labels["published"].configure(text=str(published))
        self.stats_labels["failed"].configure(text=str(failed))

    def refresh_drafts(self) -> None:
        self.drafts_all = store.list_drafts()
        status_filter = self.filter_status.get()
        self.drafts = [
            d for d in self.drafts_all
            if status_filter == "all" or d.status.value == status_filter
        ]
        selected = self.drafts_tree.selection()
        for item in self.drafts_tree.get_children():
            self.drafts_tree.delete(item)
        comm_map = {c.id: c.name for c in self.communities}
        for draft in self.drafts:
            comm_names = ", ".join(comm_map.get(cid, cid) for cid in draft.community_ids)
            self.drafts_tree.insert(
                "", "end", iid=draft.id,
                values=(draft.status.value, comm_names, self._fmt_dt(draft.created_at)),
            )
        if self.drafts:
            keep = (
                selected[0] if selected and any(d.id == selected[0] for d in self.drafts)
                else self.drafts[0].id
            )
            self.drafts_tree.selection_set(keep)
        self.show_draft_details()

    def _refresh_communities_tree(self) -> None:
        for item in self.comm_tree.get_children():
            self.comm_tree.delete(item)
        for c in self.communities:
            self.comm_tree.insert("", "end", iid=c.id, values=(c.name, c.screen_name, c.vk_group_id))

    def _refresh_comm_checkboxes(self) -> None:
        for w in self.comm_checkboxes_frame.winfo_children():
            w.destroy()
        self.comm_check_vars = {}
        if not self.communities:
            ttk.Label(
                self.comm_checkboxes_frame,
                text="Сначала добавь сообщества на вкладке «Сообщества».",
                foreground=self.MUTED,
            ).pack(anchor="w", pady=4)
            return
        for c in self.communities:
            var = tk.BooleanVar(value=False)
            self.comm_check_vars[c.id] = var
            ttk.Checkbutton(
                self.comm_checkboxes_frame,
                text=f"{c.name}  (vk.com/{c.screen_name})",
                variable=var,
            ).pack(anchor="w", pady=3)

    # ──────────────────────────── Export ──────────────────────────

    def export_csv(self) -> None:
        if not self.drafts:
            messagebox.showwarning("Нет данных", "Нет черновиков для экспорта.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=(("CSV", "*.csv"),), initialfile="drafts.csv")
        if not path:
            return
        rows = self._export_rows()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        messagebox.showinfo("Готово", f"Сохранено: {path}")

    def export_excel(self) -> None:
        if not self.drafts:
            messagebox.showwarning("Нет данных", "Нет черновиков для экспорта.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                            filetypes=(("Excel", "*.xlsx"),), initialfile="drafts.xlsx")
        if not path:
            return
        rows = self._export_rows()
        wb = Workbook()
        ws = wb.active
        ws.title = "Drafts"
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row[h] for h in headers])
        ws.freeze_panes = "A2"
        wb.save(path)
        messagebox.showinfo("Готово", f"Сохранено: {path}")

    def _export_rows(self) -> list[dict[str, str]]:
        comm_map = {c.id: c.name for c in self.communities}
        return [
            {
                "draft_id": d.id,
                "status": d.status.value,
                "communities": ", ".join(comm_map.get(cid, cid) for cid in d.community_ids),
                "created_at": self._fmt_dt(d.created_at),
                "moderation_note": d.moderation_note or "",
                "text": d.text,
            }
            for d in self.drafts
        ]

    # ──────────────────────────── Helpers ─────────────────────────

    def _update_char_count(self, _event=None) -> None:
        n = len(self.compose_text.get("1.0", "end").strip())
        color = self.ERR if n > 4000 else self.MUTED
        self.char_count_label.configure(text=f"{n} / 4000", foreground=color)

    def _make_readonly_text(self, parent, height: int) -> tk.Text:
        w = tk.Text(parent, height=height, wrap="word",
                    bg=self.INPUT, fg=self.TEXT, insertbackground=self.TEXT,
                    relief="flat", padx=12, pady=10)
        w.configure(state="disabled")
        return w

    def _make_editor_text(self, parent, height: int) -> tk.Text:
        return tk.Text(parent, height=height, wrap="word",
                       bg=self.INPUT, fg=self.TEXT, insertbackground=self.TEXT,
                       relief="flat", padx=10, pady=8, undo=True)

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _set_editor_text(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    @staticmethod
    def _fmt_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M")


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
