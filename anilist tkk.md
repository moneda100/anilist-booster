#!/usr/bin/env python3
"""
AniList Desktop App — ttkbootstrap
Requiere: pip install ttkbootstrap requests Pillow
"""

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame
import tkinter as tk
from tkinter import messagebox
from tkinter import BOTH, LEFT, RIGHT, TOP, BOTTOM, X, Y, W, E, N, S, HORIZONTAL, VERTICAL, END, WORD
from typing import Optional
import requests
import threading
import webbrowser
import json
import os
import random
from PIL import Image, ImageTk
from io import BytesIO

# Compatibilidad Pillow antiguo/nuevo
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.ANTIALIAS  # type: ignore[attr-defined]

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN  ←  pon tu Client ID aquí
# ──────────────────────────────────────────────────────────────
CLIENT_ID   = "37848"   # https://anilist.co/settings/developer
TOKEN_FILE  = "anilist_token.json"
ANILIST_API = "https://graphql.anilist.co"
PLACEHOLDER = "https://via.placeholder.com/80x115/2d2d2d/white?text=No+img"

# ──────────────────────────────────────────────────────────────
# QUERIES GraphQL
# ──────────────────────────────────────────────────────────────
Q_VIEWER = """
query {
  Viewer {
    id name
    avatar { large }
    bannerImage
    statistics {
      anime { count minutesWatched episodesWatched }
      manga { count chaptersRead volumesRead }
    }
    favourites {
      anime { nodes { title { romaji } } }
    }
  }
}"""

Q_USER_LIST = """
query ($userId: Int, $type: MediaType) {
  MediaListCollection(userId: $userId, type: $type, sort: UPDATED_TIME_DESC) {
    lists {
      name status
      entries {
        score progress updatedAt
        media {
          id
          title { romaji english }
          coverImage { medium }
          episodes chapters status
          averageScore genres
        }
      }
    }
  }
}"""

Q_SEARCH = """
query ($search: String, $type: MediaType) {
  Page(page: 1, perPage: 24) {
    media(search: $search, type: $type, sort: SEARCH_MATCH) {
      id
      title { romaji english }
      coverImage { medium }
      averageScore episodes chapters status genres
      description(asHtml: false)
    }
  }
}"""

Q_TRENDING = """
query ($type: MediaType) {
  Page(page: 1, perPage: 24) {
    media(sort: TRENDING_DESC, type: $type, isAdult: false) {
      id
      title { romaji english }
      coverImage { medium }
      averageScore episodes chapters trending genres
    }
  }
}"""

Q_RANDOM = """
query ($type: MediaType, $page: Int) {
  Page(page: $page, perPage: 1) {
    pageInfo { total lastPage }
    media(type: $type, sort: POPULARITY_DESC, status: FINISHED, isAdult: false) {
      id
      title { romaji english }
      coverImage { large }
      averageScore episodes chapters genres
      description(asHtml: false)
    }
  }
}"""

# ──────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────
def gql(query: str, variables: Optional[dict] = None, token: Optional[str] = None) -> Optional[dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(
            ANILIST_API,
            json={"query": query, "variables": variables or {}},
            headers=headers,
            timeout=15
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            print("GQL errors:", data["errors"])
            return None
        return data.get("data")
    except Exception as e:
        print(f"API error: {e}")
        return None


def load_image(url: str, size=(80, 115)) -> Optional[ImageTk.PhotoImage]:
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).resize(size, _RESAMPLE)
        return ImageTk.PhotoImage(img)
    except:
        return None


def truncate(text: str, n=40) -> str:
    return text[:n] + "…" if text and len(text) > n else (text or "—")


def title_of(media) -> str:
    t = media.get("title", {})
    return t.get("romaji") or t.get("english") or "Sin título"


def save_token(token: str):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token}, f)


def load_token() -> Optional[str]:
    if os.path.exists(TOKEN_FILE):
        try:
            return json.load(open(TOKEN_FILE))["token"]
        except:
            pass
    return None


# ──────────────────────────────────────────────────────────────
# VENTANA DE DETALLE
# ──────────────────────────────────────────────────────────────
class DetailWindow(tk.Toplevel):
    def __init__(self, parent, media: dict, token=None):
        super().__init__(parent)
        self.title(title_of(media))
        self.geometry("600x520")
        self.configure(bg="#1a1a2e")
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=20, bootstyle="dark")
        frame.pack(fill=BOTH, expand=True)

        # Imagen
        img_url = (media.get("coverImage") or {}).get("large") or \
                  (media.get("coverImage") or {}).get("medium")
        self._img = None
        if img_url:
            def _load():
                ph = load_image(img_url, (150, 215))
                if ph:
                    self._img = ph
                    lbl.configure(image=ph)
            lbl = ttk.Label(frame, bootstyle="dark")
            lbl.pack(side=LEFT, anchor=N, padx=(0, 20))
            threading.Thread(target=_load, daemon=True).start()

        info = ttk.Frame(frame, bootstyle="dark")
        info.pack(side=LEFT, fill=BOTH, expand=True)

        ttk.Label(info, text=title_of(media), font=("Helvetica", 14, "bold"),
                  bootstyle="info", wraplength=380).pack(anchor=W)

        eng = (media.get("title") or {}).get("english", "")
        if eng and eng != title_of(media):
            ttk.Label(info, text=eng, font=("Helvetica", 10),
                      bootstyle="secondary").pack(anchor=W)

        ttk.Separator(info).pack(fill=X, pady=8)

        meta = [
            ("⭐ Score",   f"{media.get('averageScore', '?')}/100"),
            ("📺 Eps/Cap", str(media.get("episodes") or media.get("chapters") or "?")),
            ("📌 Estado",  media.get("status", "?")),
            ("🎭 Géneros", ", ".join((media.get("genres") or [])[:4])),
        ]
        for k, v in meta:
            row = ttk.Frame(info, bootstyle="dark")
            row.pack(fill=X, pady=2)
            ttk.Label(row, text=k, width=14, bootstyle="secondary",
                      font=("Helvetica", 9, "bold")).pack(side=LEFT)
            ttk.Label(row, text=v, bootstyle="light",
                      wraplength=240).pack(side=LEFT)

        ttk.Separator(info).pack(fill=X, pady=8)

        desc = media.get("description") or "Sin descripción disponible."
        desc = desc[:600] + "…" if len(desc) > 600 else desc
        ttk.Label(info, text=desc, wraplength=380, justify=LEFT,
                  bootstyle="light", font=("Helvetica", 9)).pack(anchor=W)

        ttk.Button(info, text="Ver en AniList", bootstyle="info-outline",
                   command=lambda: webbrowser.open(
                       f"https://anilist.co/anime/{media.get('id')}"
                   )).pack(anchor=W, pady=(12, 0))


# ──────────────────────────────────────────────────────────────
# TARJETA DE MEDIA (reutilizable)
# ──────────────────────────────────────────────────────────────
class MediaCard(ttk.Frame):
    def __init__(self, parent, media: dict, token=None, extra_text="", **kw):
        super().__init__(parent, bootstyle="dark", **kw)
        self.media  = media
        self.token  = token
        self._img   = None
        self.configure(cursor="hand2")

        # Imagen
        img_lbl = ttk.Label(self, bootstyle="dark")
        img_lbl.pack(side=LEFT, padx=(6, 8), pady=6)

        img_url = (media.get("coverImage") or {}).get("medium")
        if img_url:
            def _load():
                ph = load_image(img_url, (56, 80))
                if ph:
                    self._img = ph
                    img_lbl.configure(image=ph)
            threading.Thread(target=_load, daemon=True).start()

        # Texto
        txt = ttk.Frame(self, bootstyle="dark")
        txt.pack(side=LEFT, fill=BOTH, expand=True, pady=6)

        ttk.Label(txt, text=truncate(title_of(media), 38),
                  font=("Helvetica", 10, "bold"),
                  bootstyle="info").pack(anchor=W)

        score = media.get("averageScore", "?")
        eps   = media.get("episodes") or media.get("chapters") or "?"
        genres = ", ".join((media.get("genres") or [])[:2])
        ttk.Label(txt, text=f"⭐ {score}  •  📺 {eps}  {genres}",
                  font=("Helvetica", 8), bootstyle="secondary").pack(anchor=W)

        if extra_text:
            ttk.Label(txt, text=extra_text, font=("Helvetica", 8),
                      bootstyle="warning").pack(anchor=W)

        # Clic → detalle
        for w in (self, img_lbl, txt):
            w.bind("<Button-1>", self._open_detail)
        for child in txt.winfo_children():
            child.bind("<Button-1>", self._open_detail)

        ttk.Separator(self, orient=HORIZONTAL).pack(side=BOTTOM, fill=X)

    def _open_detail(self, _=None):
        DetailWindow(self.winfo_toplevel(), self.media, self.token)


# ──────────────────────────────────────────────────────────────
# PESTAÑAS PRINCIPALES
# ──────────────────────────────────────────────────────────────
class ListTab(ttk.Frame):
    """Pestaña: Mi lista de anime o manga"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app

        ctrl = ttk.Frame(self, bootstyle="dark", padding=(10, 8))
        ctrl.pack(fill=X)

        ttk.Label(ctrl, text="Tipo:", bootstyle="light").pack(side=LEFT, padx=(0, 4))
        self.type_var = tk.StringVar(value="ANIME")
        for t in ("ANIME", "MANGA"):
            ttk.Radiobutton(ctrl, text=t, variable=self.type_var,
                            value=t, bootstyle="info-toolbutton",
                            command=self.load).pack(side=LEFT, padx=2)

        self.status_var = tk.StringVar(value="CURRENT")
        status_opts = [("Viendo", "CURRENT"), ("Completado", "COMPLETED"),
                       ("En pausa", "PAUSED"), ("Dropeado", "DROPPED"),
                       ("Plan", "PLANNING")]
        ttk.Label(ctrl, text="  Estado:", bootstyle="light").pack(side=LEFT, padx=(12, 4))
        self.status_cb = ttk.Combobox(ctrl, textvariable=self.status_var, width=12,
                                       values=[s[0] for s in status_opts], state="readonly")
        self.status_cb.pack(side=LEFT, padx=2)
        self._status_map = {s[0]: s[1] for s in status_opts}
        self._status_map_inv = {s[1]: s[0] for s in status_opts}
        self.status_cb.set("Viendo")
        self.status_cb.bind("<<ComboboxSelected>>", lambda _: self.load())

        ttk.Button(ctrl, text="↺ Recargar", bootstyle="info-outline",
                   command=self.load).pack(side=RIGHT, padx=6)

        self.scroll = ScrolledFrame(self, bootstyle="dark", autohide=True)
        self.scroll.pack(fill=BOTH, expand=True)
        self.inner = self.scroll.container

        self.status_lbl = ttk.Label(self, text="Inicia sesión para ver tu lista",
                                    bootstyle="secondary")
        self.status_lbl.pack(pady=20)

    def load(self):
        if not self.app.token or not self.app.user_id:
            return
        self.status_lbl.configure(text="Cargando…")
        for w in self.inner.winfo_children():
            w.destroy()
        media_type = self.type_var.get()
        threading.Thread(target=self._fetch, args=(media_type,), daemon=True).start()

    def _fetch(self, media_type):
        data = gql(Q_USER_LIST,
                   {"userId": self.app.user_id, "type": media_type},
                   self.app.token)
        self.after(0, self._render, data)

    def _render(self, data):
        self.status_lbl.configure(text="")
        if not data:
            self.status_lbl.configure(text="Error al cargar la lista.")
            return
        lists = data.get("MediaListCollection", {}).get("lists", [])
        target_status = self._status_map.get(self.status_cb.get(), "CURRENT")

        entries = []
        for lst in lists:
            if lst.get("status") == target_status:
                entries = lst.get("entries", [])
                break

        if not entries:
            self.status_lbl.configure(
                text=f"No hay entradas en '{self.status_cb.get()}'.")
            return

        self.status_lbl.configure(text=f"{len(entries)} entradas")
        for e in entries:
            media = e.get("media", {})
            prog  = e.get("progress", 0)
            score = e.get("score", 0)
            extra = f"Progreso: {prog}  •  Tu score: {score or '—'}"
            card  = MediaCard(self.inner, media, self.app.token, extra)
            card.pack(fill=X, padx=4, pady=2)


class SearchTab(ttk.Frame):
    """Pestaña: Buscar"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app

        ctrl = ttk.Frame(self, bootstyle="dark", padding=(10, 8))
        ctrl.pack(fill=X)

        self.search_var = tk.StringVar()
        entry = ttk.Entry(ctrl, textvariable=self.search_var, width=32,
                          bootstyle="info")
        entry.pack(side=LEFT, padx=(0, 6))
        entry.bind("<Return>", lambda _: self.search())

        self.type_var = tk.StringVar(value="ANIME")
        for t in ("ANIME", "MANGA"):
            ttk.Radiobutton(ctrl, text=t, variable=self.type_var,
                            value=t, bootstyle="info-toolbutton").pack(side=LEFT, padx=2)

        ttk.Button(ctrl, text="🔍 Buscar", bootstyle="info",
                   command=self.search).pack(side=LEFT, padx=8)

        self.scroll = ScrolledFrame(self, bootstyle="dark", autohide=True)
        self.scroll.pack(fill=BOTH, expand=True)
        self.inner = self.scroll.container

        self.status_lbl = ttk.Label(self, text="Escribe algo y busca…",
                                    bootstyle="secondary")
        self.status_lbl.pack(pady=20)

    def search(self):
        q = self.search_var.get().strip()
        if not q:
            return
        self.status_lbl.configure(text="Buscando…")
        for w in self.inner.winfo_children():
            w.destroy()
        threading.Thread(target=self._fetch,
                         args=(q, self.type_var.get()), daemon=True).start()

    def _fetch(self, q, media_type):
        data = gql(Q_SEARCH, {"search": q, "type": media_type}, self.app.token)
        self.after(0, self._render, data)

    def _render(self, data):
        self.status_lbl.configure(text="")
        results = (data or {}).get("Page", {}).get("media", [])
        if not results:
            self.status_lbl.configure(text="Sin resultados.")
            return
        self.status_lbl.configure(text=f"{len(results)} resultados")
        for m in results:
            MediaCard(self.inner, m, self.app.token).pack(fill=X, padx=4, pady=2)


class TrendingTab(ttk.Frame):
    """Pestaña: Tendencias"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app

        ctrl = ttk.Frame(self, bootstyle="dark", padding=(10, 8))
        ctrl.pack(fill=X)
        ttk.Label(ctrl, text="Tendencias en AniList", font=("Helvetica", 12, "bold"),
                  bootstyle="info").pack(side=LEFT)

        self.type_var = tk.StringVar(value="ANIME")
        for t in ("ANIME", "MANGA"):
            ttk.Radiobutton(ctrl, text=t, variable=self.type_var,
                            value=t, bootstyle="info-toolbutton",
                            command=self.load).pack(side=LEFT, padx=6)

        ttk.Button(ctrl, text="↺", bootstyle="secondary-outline",
                   width=3, command=self.load).pack(side=RIGHT, padx=6)

        self.scroll = ScrolledFrame(self, bootstyle="dark", autohide=True)
        self.scroll.pack(fill=BOTH, expand=True)
        self.inner = self.scroll.container

        self.status_lbl = ttk.Label(self, text="Cargando tendencias…",
                                    bootstyle="secondary")
        self.status_lbl.pack(pady=20)
        self.load()

    def load(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.status_lbl.configure(text="Cargando…")
        threading.Thread(target=self._fetch,
                         args=(self.type_var.get(),), daemon=True).start()

    def _fetch(self, media_type):
        data = gql(Q_TRENDING, {"type": media_type}, self.app.token)
        self.after(0, self._render, data)

    def _render(self, data):
        self.status_lbl.configure(text="")
        results = (data or {}).get("Page", {}).get("media", [])
        if not results:
            self.status_lbl.configure(text="Sin datos de tendencias.")
            return
        for i, m in enumerate(results, 1):
            extra = f"#{i} tendencia  •  🔥 {m.get('trending', '?')}"
            MediaCard(self.inner, m, self.app.token, extra).pack(
                fill=X, padx=4, pady=2)


class ProfileTab(ttk.Frame):
    """Pestaña: Perfil y estadísticas"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app
        self._avatar_img = None

        self.placeholder = ttk.Label(self, text="Inicia sesión para ver tu perfil.",
                                     bootstyle="secondary")
        self.placeholder.pack(expand=True)

    def render(self, viewer: dict):
        for w in self.winfo_children():
            w.destroy()

        scroll = ScrolledFrame(self, bootstyle="dark", autohide=True)
        scroll.pack(fill=BOTH, expand=True)
        c = scroll.container

        # Avatar + nombre
        header = ttk.Frame(c, bootstyle="dark", padding=20)
        header.pack(fill=X)

        av_lbl = ttk.Label(header, bootstyle="dark")
        av_lbl.pack(side=LEFT, padx=(0, 16))

        av_url = (viewer.get("avatar") or {}).get("large")
        if av_url:
            def _load():
                ph = load_image(av_url, (90, 90))
                if ph:
                    self._avatar_img = ph
                    av_lbl.configure(image=ph)
            threading.Thread(target=_load, daemon=True).start()

        name_frame = ttk.Frame(header, bootstyle="dark")
        name_frame.pack(side=LEFT)
        ttk.Label(name_frame, text=viewer.get("name", "Usuario"),
                  font=("Helvetica", 20, "bold"), bootstyle="info").pack(anchor=W)
        ttk.Label(name_frame, text="Perfil de AniList",
                  bootstyle="secondary").pack(anchor=W)
        ttk.Button(name_frame, text="Ver perfil en web", bootstyle="info-outline",
                   command=lambda: webbrowser.open(
                       f"https://anilist.co/user/{viewer.get('name')}"
                   )).pack(anchor=W, pady=(8, 0))

        ttk.Separator(c).pack(fill=X, padx=20, pady=4)

        # Estadísticas
        stats = viewer.get("statistics", {})
        anime_s = stats.get("anime", {})
        manga_s = stats.get("manga", {})

        cards_frame = ttk.Frame(c, bootstyle="dark", padding=(20, 10))
        cards_frame.pack(fill=X)

        def stat_card(parent, title, items):
            f = ttk.Labelframe(parent, text=title, bootstyle="info", padding=14)
            f.pack(side=LEFT, expand=True, fill=BOTH, padx=8)
            for label, val in items:
                row = ttk.Frame(f, bootstyle="dark")
                row.pack(fill=X, pady=3)
                ttk.Label(row, text=label, bootstyle="secondary",
                          width=18).pack(side=LEFT)
                ttk.Label(row, text=str(val), bootstyle="light",
                          font=("Helvetica", 10, "bold")).pack(side=LEFT)

        hours = anime_s.get("minutesWatched", 0) // 60
        stat_card(c, "🎬 Anime", [
            ("Series vistas",   anime_s.get("count", 0)),
            ("Episodios",       anime_s.get("episodesWatched", 0)),
            ("Horas vistas",    f"{hours}h"),
        ])
        stat_card(c, "📖 Manga", [
            ("Series leídas",   manga_s.get("count", 0)),
            ("Capítulos",       manga_s.get("chaptersRead", 0)),
            ("Volúmenes",       manga_s.get("volumesRead", 0)),
        ])

        # Favoritos
        favs = viewer.get("favourites", {}).get("anime", {}).get("nodes", [])
        if favs:
            ttk.Separator(c).pack(fill=X, padx=20, pady=4)
            ttk.Label(c, text="❤️  Anime Favoritos",
                      font=("Helvetica", 11, "bold"),
                      bootstyle="info", padding=(20, 8)).pack(anchor=W)
            fav_frame = ttk.Frame(c, bootstyle="dark", padding=(20, 0))
            fav_frame.pack(fill=X)
            for f in favs[:8]:
                t = (f.get("title") or {}).get("romaji", "?")
                ttk.Label(fav_frame, text=f"• {t}",
                          bootstyle="light").pack(anchor=W)


# ──────────────────────────────────────────────────────────────
# VENTANA DE LOGIN
# ──────────────────────────────────────────────────────────────
class LoginWindow(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.title("Iniciar sesión en AniList")
        self.geometry("500x650")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)
        self.on_success = on_success
        self.grab_set()

        f = ttk.Frame(self, bootstyle="dark", padding=30)
        f.pack(fill=BOTH, expand=True)

        ttk.Label(f, text="🔐  Conectar con AniList",
                  font=("Helvetica", 15, "bold"), bootstyle="info").pack(pady=(0, 6))

        ttk.Label(f,
            text=(
                "Para autenticarte necesitas un Client ID de AniList.\n\n"
                "1. Ve a anilist.co/settings/developer\n"
                "2. Crea una nueva app (Redirect URL: https://anilist.co/api/v2/oauth/pin)\n"
                "3. Copia el Client ID y pégalo abajo\n"
                "4. Haz clic en 'Abrir autorización'\n"
                "5. Copia el token que te da AniList y pégalo en el segundo campo"
            ),
            bootstyle="secondary", justify=LEFT, wraplength=400
        ).pack(pady=8)

        ttk.Label(f, text="Client ID:", bootstyle="light").pack(anchor=W)
        self.cid_var = tk.StringVar(value=CLIENT_ID if CLIENT_ID != "YOUR_CLIENT_ID" else "")
        ttk.Entry(f, textvariable=self.cid_var, width=38, bootstyle="info").pack(fill=X)

        ttk.Button(f, text="🌐  Abrir autorización en el navegador",
                   bootstyle="info-outline", command=self._open_oauth).pack(fill=X, pady=(10, 4))

        ttk.Label(f, text="Token de acceso:", bootstyle="light").pack(anchor=W)
        self.token_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.token_var, width=38,
                  show="•", bootstyle="info").pack(fill=X)

        ttk.Button(f, text="✅  Iniciar sesión", bootstyle="success",
                   command=self._login).pack(fill=X, pady=(12, 0))

    def _open_oauth(self):
        cid = self.cid_var.get().strip()
        if not cid:
            messagebox.showwarning("Falta Client ID", "Ingresa tu Client ID primero.",
                                   parent=self)
            return
        url = (f"https://anilist.co/api/v2/oauth/authorize"
               f"?client_id={cid}&response_type=token")
        webbrowser.open(url)

    def _login(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("Falta token", "Pega el token de acceso.", parent=self)
            return
        data = gql(Q_VIEWER, token=token)
        if not data or "Viewer" not in data:
            messagebox.showerror("Error", "Token inválido o sin conexión.", parent=self)
            return
        save_token(token)
        self.destroy()
        self.on_success(token, data["Viewer"])


# ──────────────────────────────────────────────────────────────
# VENTANA PRINCIPAL
# ──────────────────────────────────────────────────────────────
class AniListApp(ttk.Window):
    def __init__(self):
        super().__init__(
            title="AniList Desktop",
            themename="darkly",
            size=(920, 680),
            minsize=(800, 560),
        )
        self.token   : Optional[str] = None
        self.user_id : Optional[int] = None
        self._build_ui()
        self._try_auto_login()

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        # Barra superior
        topbar = ttk.Frame(self, bootstyle="dark", padding=(12, 8))
        topbar.pack(fill=X)

        ttk.Label(topbar, text="AniList", font=("Helvetica", 18, "bold"),
                  bootstyle="info").pack(side=LEFT)
        self.user_lbl = ttk.Label(topbar, text="Sin sesión",
                                  bootstyle="secondary")
        self.user_lbl.pack(side=LEFT, padx=16)

        # Botón aleatorio
        ttk.Button(topbar, text="🎲  Anime aleatorio",
                   bootstyle="warning-outline",
                   command=lambda: self._random("ANIME")).pack(side=RIGHT, padx=4)
        ttk.Button(topbar, text="🎲  Manga aleatorio",
                   bootstyle="warning-outline",
                   command=lambda: self._random("MANGA")).pack(side=RIGHT, padx=4)
        self.login_btn = ttk.Button(topbar, text="Iniciar sesión",
                                    bootstyle="info",
                                    command=self._open_login)
        self.login_btn.pack(side=RIGHT, padx=8)

        ttk.Separator(self).pack(fill=X)

        # Tabs
        self.notebook = ttk.Notebook(self, bootstyle="dark")
        self.notebook.pack(fill=BOTH, expand=True, padx=0, pady=0)

        self.tab_list     = ListTab(self.notebook, self)
        self.tab_search   = SearchTab(self.notebook, self)
        self.tab_trending = TrendingTab(self.notebook, self)
        self.tab_profile  = ProfileTab(self.notebook, self)

        self.notebook.add(self.tab_list,     text="  📋 Mi Lista  ")
        self.notebook.add(self.tab_search,   text="  🔍 Buscar  ")
        self.notebook.add(self.tab_trending, text="  🔥 Tendencias  ")
        self.notebook.add(self.tab_profile,  text="  👤 Perfil  ")

    # ── AUTH ────────────────────────────────────────────────
    def _try_auto_login(self):
        token = load_token()
        if not token:
            return
        def _check():
            data = gql(Q_VIEWER, token=token)
            if data and "Viewer" in data:
                self.after(0, self._on_login, token, data["Viewer"])
        threading.Thread(target=_check, daemon=True).start()

    def _open_login(self):
        LoginWindow(self, self._on_login)

    def _on_login(self, token: str, viewer: dict):
        self.token   = token
        self.user_id = viewer.get("id")
        name = viewer.get("name", "Usuario")
        self.user_lbl.configure(text=f"👤  {name}", bootstyle="info")
        self.login_btn.configure(text="Cerrar sesión",
                                 command=self._logout, bootstyle="danger-outline")
        self.tab_list.load()
        self.tab_profile.render(viewer)

    def _logout(self):
        self.token   = None
        self.user_id = None
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.user_lbl.configure(text="Sin sesión", bootstyle="secondary")
        self.login_btn.configure(text="Iniciar sesión",
                                 command=self._open_login, bootstyle="info")

    # ── ALEATORIO ───────────────────────────────────────────
    def _random(self, media_type: str):
        page = random.randint(1, 50)
        threading.Thread(target=self._fetch_random,
                         args=(media_type, page), daemon=True).start()

    def _fetch_random(self, media_type: str, page: int):
        data = gql(Q_RANDOM, {"type": media_type, "page": page}, self.token or "")
        items = (data or {}).get("Page", {}).get("media", [])
        if items:
            self.after(0, lambda: DetailWindow(self, items[0], self.token))
        else:
            self.after(0, lambda: messagebox.showinfo(
                "Sin resultado", "No se encontró un resultado aleatorio."))


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AniListApp()
    app.mainloop()