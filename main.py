#!/usr/bin/env python3
"""
AniList Desktop App — ttkbootstrap
Requiere: pip install ttkbootstrap requests Pillow
"""

import ttkbootstrap as ttk
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
CLIENT_ID   = "YOUR_CLIENT_ID"   # https://anilist.co/settings/developer
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
query ($search: String, $type: MediaType, $page: Int) {
  Page(page: $page, perPage: 24) {
    pageInfo { lastPage currentPage total }
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
query ($type: MediaType, $page: Int) {
  Page(page: $page, perPage: 24) {
    pageInfo { lastPage currentPage total }
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

Q_SINGLE_MEDIA = """
query ($mediaId: Int) {
  Media (id: $mediaId) {
    id
    title { romaji english }
    coverImage { large }
    episodes chapters status format
    averageScore genres description
    mediaListEntry {
      id status score(format: POINT_100) progress
    }
  }
}"""

M_SAVE_LIST_ENTRY = """
mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int, $score: Float) {
  SaveMediaListEntry (mediaId: $mediaId, status: $status, progress: $progress, score: $score) {
    id status progress score(format: POINT_100)
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


# ──────────────────────────────────────────────────────────────
# SCROLL CON MOUSE + TECLADO — helper universal
# ──────────────────────────────────────────────────────────────
def _bind_mousewheel(widget: tk.Widget, canvas: tk.Canvas):
    """Bindea scroll del mouse a un canvas desde cualquier widget hijo."""

    def _on_mousewheel(event):
        # Windows / macOS
        if hasattr(event, 'delta') and event.delta:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")

    def _bind_recursive(w):
        try:
            children = w.winfo_children()
        except tk.TclError:
            return

        w.bind("<MouseWheel>", _on_mousewheel, add="+")   # Windows/macOS
        w.bind("<Button-4>", _on_mousewheel, add="+")     # Linux scroll up
        w.bind("<Button-5>", _on_mousewheel, add="+")     # Linux scroll down

        for child in children:
            _bind_recursive(child)

    _bind_recursive(widget)


def make_scroll_area(parent, bg="#1e1e2e"):
    """Crea un área de scroll con Canvas + Frame interior.
    Retorna (canvas, inner_frame).
    El canvas tiene su propio scroll y se puede controlar con canvas.yview_scroll().
    """
    canvas = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0)
    canvas.pack(fill=BOTH, expand=True)

    inner = ttk.Frame(canvas, bootstyle="dark")
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfig(window_id, width=event.width)

    inner.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    return canvas, inner


def refresh_scroll(canvas):
    """Actualiza el scrollregion del canvas después de agregar/quitar items."""
    try:
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
    except tk.TclError:
        pass

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
    def __init__(self, parent, media: dict, token=None, on_save=None):
        super().__init__(parent)
        self.media_id = media.get("id")
        self.token = token
        self.on_save = on_save
        self.media = media # info inicial
        self.title(f"Detalle: {title_of(media)}")
        self.geometry("700x620")
        self.configure(bg="#1a1a2e")
        self.resizable(False, False)

        # Variables para controles
        self.status_var = tk.StringVar(value="Viendo/Leyendo")
        self.progress_var = tk.IntVar(value=0)
        self.score_var = tk.IntVar(value=0)
        self.remaining_lbl = None

        self.frame = ttk.Frame(self, padding=20, bootstyle="dark")
        self.frame.pack(fill=BOTH, expand=True)

        self._render_ui()
        if self.token:
            threading.Thread(target=self._fetch_latest, daemon=True).start()

    def _render_ui(self):
        # Limpiar frame si es necesario (re-render)
        for w in self.frame.winfo_children():
            w.destroy()

        media = self.media
        
        # Imagen
        img_url = (media.get("coverImage") or {}).get("large") or \
                  (media.get("coverImage") or {}).get("medium")
        self._img = None
        if img_url:
            def _load():
                ph = load_image(img_url, (180, 260))
                if ph:
                    self._img = ph
                    try: lbl.configure(image=ph)
                    except: pass
            lbl = ttk.Label(self.frame, bootstyle="dark")
            lbl.pack(side=LEFT, anchor=N, padx=(0, 25))
            threading.Thread(target=_load, daemon=True).start()

        info = ttk.Frame(self.frame, bootstyle="dark")
        info.pack(side=LEFT, fill=BOTH, expand=True)

        # Título
        ttk.Label(info, text=title_of(media), font=("Helvetica", 16, "bold"),
                  bootstyle="info", wraplength=420).pack(anchor=W)

        eng = (media.get("title") or {}).get("title", {}).get("english", "") # corregimos acceso
        if not eng: eng = (media.get("title") or {}).get("english", "")
        if eng and eng != title_of(media):
            ttk.Label(info, text=eng, font=("Helvetica", 11),
                      bootstyle="secondary").pack(anchor=W)

        ttk.Separator(info).pack(fill=X, pady=10)

        # Meta info
        meta_frame = ttk.Frame(info, bootstyle="dark")
        meta_frame.pack(fill=X)

        total = media.get("episodes") or media.get("chapters") or "?"
        meta = [
            ("⭐ Puntaje Promedio", f"{media.get('averageScore', '?')}/100"),
            ("📺 Total Eps/Cap",  str(total)),
            ("📌 Estado Global",   media.get("status", "?").replace("_", " ")),
            ("🎭 Géneros",        ", ".join((media.get("genres") or [])[:5])),
        ]
        for k, v in meta:
            row = ttk.Frame(meta_frame, bootstyle="dark")
            row.pack(fill=X, pady=2)
            ttk.Label(row, text=k, width=18, bootstyle="secondary",
                      font=("Helvetica", 9, "bold")).pack(side=LEFT)
            ttk.Label(row, text=v, bootstyle="light", font=("Helvetica", 9),
                      wraplength=260).pack(side=LEFT)

        ttk.Separator(info).pack(fill=X, pady=10)

        # SECCIÓN DE USUARIO (Si hay token)
        if self.token:
            u_frame = ttk.Labelframe(info, text=" Mi Progreso ", padding=10, bootstyle="info")
            u_frame.pack(fill=X, pady=(0, 15))

            # Fila 1: Estado y Score
            r1 = ttk.Frame(u_frame, bootstyle="info")
            r1.pack(fill=X, pady=4)
            
            ttk.Label(r1, text="Estado:", width=8, font=("Helvetica", 9)).pack(side=LEFT)
            st_choices = ["Viendo/Leyendo", "Completado", "Pausado", "Dropeado", "Planeado", "Repitiendo"]
            st_cb = ttk.Combobox(r1, textvariable=self.status_var, values=st_choices, width=15, state="readonly")
            st_cb.pack(side=LEFT, padx=(0, 15))

            ttk.Label(r1, text="Score:", width=6, font=("Helvetica", 9)).pack(side=LEFT)
            ttk.Spinbox(r1, from_=0, to=100, textvariable=self.score_var, width=5).pack(side=LEFT)

            # Fila 2: Progreso y Faltante
            r2 = ttk.Frame(u_frame, bootstyle="info")
            r2.pack(fill=X, pady=4)

            ttk.Label(r2, text="Progreso:", width=8, font=("Helvetica", 9)).pack(side=LEFT)
            sp = ttk.Spinbox(r2, from_=0, to=9999, textvariable=self.progress_var, width=5, command=self._update_remaining)
            sp.pack(side=LEFT, padx=(0, 10))
            sp.bind("<KeyRelease>", lambda e: self._update_remaining())

            self.remaining_lbl = ttk.Label(r2, text="", font=("Helvetica", 8, "italic"), bootstyle="secondary")
            self.remaining_lbl.pack(side=LEFT)

            # Botón Guardar
            btn_s = ttk.Button(u_frame, text="💾 Guardar Cambios", bootstyle="success-outline", 
                               command=self._save_entry)
            btn_s.pack(fill=X, pady=(10, 0))

        # Descripción
        desc = media.get("description") or "Sin descripción disponible."
        desc = desc.replace("<br>", "\n").replace("<i>", "").replace("</i>", "").replace("<b>", "").replace("</b>", "")
        desc = desc[:450] + "…" if len(desc) > 450 else desc
        ttk.Label(info, text=desc, wraplength=420, justify=LEFT,
                  bootstyle="light", font=("Helvetica", 9)).pack(anchor=W, pady=10)

        # Footer
        footer = ttk.Frame(info, bootstyle="dark")
        footer.pack(fill=X, side=BOTTOM, pady=(10, 0))

        ttk.Button(footer, text="🌐 Ver en AniList", bootstyle="info-outline",
                   command=lambda: webbrowser.open(
                       f"https://anilist.co/anime/{self.media_id}"
                   )).pack(side=LEFT)

        ttk.Button(footer, text="Cerrar", bootstyle="secondary-outline",
                   command=self.destroy).pack(side=RIGHT)

    def _update_remaining(self, _=None):
        if not self.remaining_lbl: return
        total = self.media.get("episodes") or self.media.get("chapters")
        try:
            prog = self.progress_var.get()
            if total and isinstance(total, int):
                faltan = max(0, total - prog)
                self.remaining_lbl.configure(text=f"(Te faltan {faltan} para terminar)")
            else:
                self.remaining_lbl.configure(text="")
        except:
            pass

    def _fetch_latest(self):
        # Mapa de estado para UI
        st_map_rev = {
            "CURRENT": "Viendo/Leyendo",
            "COMPLETED": "Completado",
            "PAUSED": "Pausado",
            "DROPPED": "Dropeado",
            "PLANNING": "Planeado",
            "REPEATING": "Repitiendo"
        }
        res = gql(Q_SINGLE_MEDIA, {"mediaId": self.media_id}, self.token)
        if res and res.get("Media"):
            self.media = res["Media"]
            entry = self.media.get("mediaListEntry")
            if entry:
                self.status_var.set(st_map_rev.get(entry["status"], "Viendo/Leyendo"))
                self.progress_var.set(entry.get("progress", 0))
                self.score_var.set(entry.get("score") or 0)
                self.after(0, self._render_ui)
                self.after(0, self._update_remaining)

    def _save_entry(self):
        st_map = {
            "Viendo/Leyendo": "CURRENT",
            "Completado": "COMPLETED",
            "Pausado": "PAUSED",
            "Dropeado": "DROPPED",
            "Planeado": "PLANNING",
            "Repitiendo": "REPEATING"
        }
        status = st_map.get(self.status_var.get(), "CURRENT")
        prog = self.progress_var.get()
        score = float(self.score_var.get())

        def _do():
            vars = {
                "mediaId": self.media_id,
                "status": status,
                "progress": prog,
                "score": score
            }
            print(f"DEBUG: Saving entry with vars: {vars}")
            res = gql(M_SAVE_LIST_ENTRY, vars, self.token)
            if res and res.get("SaveMediaListEntry"):
                self.after(0, lambda: messagebox.showinfo("Éxito", "Cambios guardados correctamente."))
                if self.on_save:
                    self.after(0, self.on_save)
            else:
                self.after(0, lambda: messagebox.showerror("Error", "No se pudieron guardar los cambios.\nRevisa la consola para más detalles."))

        threading.Thread(target=_do, daemon=True).start()


# ──────────────────────────────────────────────────────────────
# TARJETA DE MEDIA (reutilizable)
# ──────────────────────────────────────────────────────────────
class MediaCard(ttk.Frame):
    def __init__(self, parent, media: dict, token=None, extra_text="", on_save=None, **kw):
        super().__init__(parent, bootstyle="dark", **kw)
        self.media  = media
        self.token  = token
        self.on_save = on_save
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
                    try:
                        img_lbl.configure(image=ph)
                    except tk.TclError:
                        pass
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
        DetailWindow(self.winfo_toplevel(), self.media, self.token, on_save=self.on_save)


# ──────────────────────────────────────────────────────────────
# PESTAÑAS PRINCIPALES
# ──────────────────────────────────────────────────────────────
class ListTab(ttk.Frame):
    """Pestaña: Mi lista de anime o manga"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app
        self.all_entries = []
        self.page = 1
        self.per_page = 24

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

        # Barra de navegación
        self.nav = ttk.Frame(self, bootstyle="dark", padding=(10, 5))
        self.nav.pack(side=BOTTOM, fill=X)
        
        self.btn_prev = ttk.Button(self.nav, text="❮", bootstyle="info-outline", command=lambda: self.go_page(-1))
        self.btn_prev.pack(side=LEFT, padx=5)
        
        self.page_var = tk.StringVar(value="1")
        self.page_ent = ttk.Entry(self.nav, textvariable=self.page_var, width=5, justify="center")
        self.page_ent.pack(side=LEFT, padx=5)
        self.page_ent.bind("<Return>", lambda e: self.jump_page())
        
        self.lbl_total = ttk.Label(self.nav, text="de 1", bootstyle="secondary")
        self.lbl_total.pack(side=LEFT, padx=5)
        
        self.btn_next = ttk.Button(self.nav, text="❯", bootstyle="info-outline", command=lambda: self.go_page(1))
        self.btn_next.pack(side=LEFT, padx=5)

        # Separador visual
        ttk.Separator(self.nav, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)

        # Botones de scroll arriba/abajo
        ttk.Button(self.nav, text="▲", bootstyle="secondary-outline", width=3,
                   command=lambda: self._scroll_content(-5)).pack(side=LEFT, padx=2)
        ttk.Button(self.nav, text="▼", bootstyle="secondary-outline", width=3,
                   command=lambda: self._scroll_content(5)).pack(side=LEFT, padx=2)

        # Área de contenido con scroll
        self.canvas, self.inner = make_scroll_area(self)

        self.status_lbl = ttk.Label(self, text="Inicia sesión para ver tu lista",
                                    bootstyle="secondary")
        self.status_lbl.pack(pady=20)

    def _scroll_content(self, units):
        """Desplaza el canvas arriba/abajo."""
        try:
            self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass

    def _scroll_to_top(self):
        try:
            self.canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def go_page(self, step):
        self.page = max(1, min(self.page + step, self.get_last_page()))
        self.page_var.set(str(self.page))
        self._scroll_to_top()
        self._render_page()

    def jump_page(self):
        try:
            p = int(self.page_var.get())
            self.page = max(1, min(p, self.get_last_page()))
            self.page_var.set(str(self.page))
            self._scroll_to_top()
            self._render_page()
        except:
            self.page_var.set(str(self.page))

    def get_last_page(self):
        return max(1, (len(self.all_entries) + self.per_page - 1) // self.per_page)

    def load(self):
        if not self.app.token or not self.app.user_id:
            return
        self.page = 1
        self.page_var.set("1")
        self.all_entries = []
        self.status_lbl.configure(text="Cargando…")
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
        
        self.all_entries = entries
        self.lbl_total.configure(text=f"de {self.get_last_page()}")
        self._render_page()

    def _render_page(self):
        for w in self.inner.winfo_children():
            w.destroy()
        
        last = self.get_last_page()
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        page_items = self.all_entries[start:end]

        self.status_lbl.configure(text=f"{len(self.all_entries)} entradas en total (Página {self.page} de {last})")
        for e in page_items:
            media = e.get("media", {})
            prog  = e.get("progress", 0)
            score = e.get("score", 0)
            extra = f"Progreso: {prog}  •  Tu score: {score or '—'}"
            card  = MediaCard(self.inner, media, self.app.token, extra, on_save=lambda: self.load(reset_page=False))
            card.pack(fill=X, padx=4, pady=2)
        refresh_scroll(self.canvas)

class SearchTab(ttk.Frame):
    """Pestaña: Buscar"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app
        self.page = 1
        self.last_page = 1

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

        # Barra de navegación
        self.nav = ttk.Frame(self, bootstyle="dark", padding=(10, 5))
        self.nav.pack(side=BOTTOM, fill=X)
        
        self.btn_prev = ttk.Button(self.nav, text="❮", bootstyle="info-outline", command=lambda: self.go_page(-1))
        self.btn_prev.pack(side=LEFT, padx=5)
        
        self.page_var = tk.StringVar(value="1")
        self.page_ent = ttk.Entry(self.nav, textvariable=self.page_var, width=5, justify="center")
        self.page_ent.pack(side=LEFT, padx=5)
        self.page_ent.bind("<Return>", lambda e: self.jump_page())
        
        self.lbl_total = ttk.Label(self.nav, text="de 1", bootstyle="secondary")
        self.lbl_total.pack(side=LEFT, padx=5)
        
        self.btn_next = ttk.Button(self.nav, text="❯", bootstyle="info-outline", command=lambda: self.go_page(1))
        self.btn_next.pack(side=LEFT, padx=5)

        # Separador visual
        ttk.Separator(self.nav, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)

        # Botones de scroll arriba/abajo
        ttk.Button(self.nav, text="▲", bootstyle="secondary-outline", width=3,
                   command=lambda: self._scroll_content(-5)).pack(side=LEFT, padx=2)
        ttk.Button(self.nav, text="▼", bootstyle="secondary-outline", width=3,
                   command=lambda: self._scroll_content(5)).pack(side=LEFT, padx=2)

        # Área de contenido con scroll
        self.canvas, self.inner = make_scroll_area(self)

        self.status_lbl = ttk.Label(self, text="Escribe algo y busca…",
                                    bootstyle="secondary")
        self.status_lbl.pack(pady=20)

    def _scroll_content(self, units):
        """Desplaza el canvas arriba/abajo."""
        try:
            self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass

    def _scroll_to_top(self):
        try:
            self.canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def go_page(self, step):
        new_p = max(1, min(self.page + step, self.last_page))
        if new_p != self.page:
            self.page = new_p
            self.page_var.set(str(self.page))
            self._scroll_to_top()
            self.search(reset_page=False)

    def jump_page(self):
        try:
            p = int(self.page_var.get())
            self.page = max(1, min(p, self.last_page))
            self.page_var.set(str(self.page))
            self._scroll_to_top()
            self.search(reset_page=False)
        except:
            self.page_var.set(str(self.page))

    def search(self, reset_page=True):
        if reset_page:
            self.page = 1
            self.page_var.set("1")
        q = self.search_var.get().strip()
        if not q:
            return
        self.status_lbl.configure(text="Buscando…")
        for w in self.inner.winfo_children():
            w.destroy()
        threading.Thread(target=self._fetch,
                         args=(q, self.type_var.get(), self.page), daemon=True).start()

    def _fetch(self, q, media_type, page):
        data = gql(Q_SEARCH, {"search": q, "type": media_type, "page": page}, self.app.token)
        self.after(0, self._render, data)

    def _render(self, data):
        self.status_lbl.configure(text="")
        page_data = (data or {}).get("Page", {})
        results = page_data.get("media", [])
        info = page_data.get("pageInfo", {})
        total = info.get("total", 0)
        self.last_page = info.get("lastPage", 1)
        self.lbl_total.configure(text=f"de {self.last_page}")

        if not results:
            self.status_lbl.configure(text="Sin resultados.")
            return
        self.status_lbl.configure(text=f"{total} resultados encontrados (Página {self.page} de {self.last_page})")
        for m in results:
            MediaCard(self.inner, m, self.app.token, on_save=lambda: self.search(reset_page=False)).pack(fill=X, padx=4, pady=2)
        refresh_scroll(self.canvas)

        


class TrendingTab(ttk.Frame):
    """Pestaña: Tendencias"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app
        self.page = 1
        self.last_page = 1

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

        # Barra de navegación
        self.nav = ttk.Frame(self, bootstyle="dark", padding=(10, 5))
        self.nav.pack(side=BOTTOM, fill=X)
        
        self.btn_prev = ttk.Button(self.nav, text="❮", bootstyle="info-outline", command=lambda: self.go_page(-1))
        self.btn_prev.pack(side=LEFT, padx=5)
        
        self.page_var = tk.StringVar(value="1")
        self.page_ent = ttk.Entry(self.nav, textvariable=self.page_var, width=5, justify="center")
        self.page_ent.pack(side=LEFT, padx=5)
        self.page_ent.bind("<Return>", lambda e: self.jump_page())
        
        self.lbl_total = ttk.Label(self.nav, text="de 1", bootstyle="secondary")
        self.lbl_total.pack(side=LEFT, padx=5)
        
        self.btn_next = ttk.Button(self.nav, text="❯", bootstyle="info-outline", command=lambda: self.go_page(1))
        self.btn_next.pack(side=LEFT, padx=5)

        # Separador visual
        ttk.Separator(self.nav, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)

        # Botones de scroll arriba/abajo
        ttk.Button(self.nav, text="▲", bootstyle="secondary-outline", width=3,
                   command=lambda: self._scroll_content(-5)).pack(side=LEFT, padx=2)
        ttk.Button(self.nav, text="▼", bootstyle="secondary-outline", width=3,
                   command=lambda: self._scroll_content(5)).pack(side=LEFT, padx=2)

        # Área de contenido con scroll
        self.canvas, self.inner = make_scroll_area(self)

        self.status_lbl = ttk.Label(self, text="Cargando tendencias…",
                                    bootstyle="secondary")
        self.status_lbl.pack(pady=20)
        self.load()

    def _scroll_content(self, units):
        """Desplaza el canvas arriba/abajo."""
        try:
            self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass

    def _scroll_to_top(self):
        try:
            self.canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def go_page(self, step):
        new_p = max(1, min(self.page + step, self.last_page))
        if new_p != self.page:
            self.page = new_p
            self.page_var.set(str(self.page))
            self._scroll_to_top()
            self.load(reset_page=False)

    def jump_page(self):
        try:
            p = int(self.page_var.get())
            self.page = max(1, min(p, self.last_page))
            self.page_var.set(str(self.page))
            self._scroll_to_top()
            self.load(reset_page=False)
        except:
            self.page_var.set(str(self.page))

    def load(self, reset_page=True):
        if reset_page:
            self.page = 1
            self.page_var.set("1")
        for w in self.inner.winfo_children():
            w.destroy()
        self.status_lbl.configure(text="Cargando…")
        threading.Thread(target=self._fetch, args=(self.type_var.get(), self.page), daemon=True).start()

    def _fetch(self, media_type, page):
        data = gql(Q_TRENDING, {"type": media_type, "page": page}, self.app.token)
        self.after(0, self._render, data)

    def _render(self, data):
        self.status_lbl.configure(text="")
        results = (data or {}).get("Page", {}).get("media", [])
        page_data = (data or {}).get("Page", {})
        results = page_data.get("media", [])
        info = page_data.get("pageInfo", {})
        total = info.get("total", 0)
        self.last_page = info.get("lastPage", 1)
        self.lbl_total.configure(text=f"de {self.last_page}")

        if not results:
            self.status_lbl.configure(text="Sin datos de tendencias.")
            return
        self.status_lbl.configure(text=f"{total} tendencias encontradas (Página {self.page} de {self.last_page})")
        for i, m in enumerate(results, 1):
            global_idx = (self.page - 1) * 24 + i
            extra = f"#{global_idx} tendencia  •  🔥 {m.get('trending', '?')}"
            MediaCard(self.inner, m, self.app.token, extra, on_save=lambda: self.load(reset_page=False)).pack(
                fill=X, padx=4, pady=2)
        refresh_scroll(self.canvas)


class ProfileTab(ttk.Frame):
    """Pestaña: Perfil y estadísticas"""
    def __init__(self, parent, app):
        super().__init__(parent, bootstyle="dark")
        self.app = app
        self._avatar_img = None

        self.placeholder = ttk.Label(self, text="Inicia sesión para ver tu perfil.",
                                     bootstyle="secondary")
        self.placeholder.pack(expand=True)

    def _scroll_content(self, units):
        """Desplaza el canvas arriba/abajo."""
        try:
            self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass

    def render(self, viewer: dict):
        for w in self.winfo_children():
            w.destroy()

        # Área de contenido con scroll
        self.canvas, c = make_scroll_area(self, bg="#1a1a2e")

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

        refresh_scroll(self.canvas)


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
            themename="vapor",
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