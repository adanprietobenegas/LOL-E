"""Ventana «Ayuda de LOL-E»: arriba, qué es la pantalla en la que estás (qué es, cuándo la verás, de dónde sale) y debajo las preguntas frecuentes con buscador.
Cada pregunta se despliega con su respuesta y un botón «Enséñamelo» que lleva a la pantalla donde está. Los datos y la búsqueda están en ayuda.py."""
import customtkinter as ctk

import ayuda
from ui_kit import PAL


class HelpWindow:
    def __init__(self, gui):
        self.gui, self.k = gui, gui.kit
        self.win = None
        self.open_id = None

    # ---- abrir y cerrar ----
    def alive(self):
        try:
            return self.win is not None and bool(self.win.winfo_exists())
        except Exception:
            return False

    def open(self, page_key=None):
        """Abre la ayuda (o la trae al frente) con la pantalla actual arriba."""
        self.page_key = page_key
        if self.alive():
            self.win.deiconify()
            self.win.lift()
            self.paint_here()
            return
        k = self.k
        win = self.win = ctk.CTkToplevel(self.gui.root)
        win.title("Ayuda de LOL-E")
        win.geometry("560x720")
        win.minsize(420, 480)
        win.configure(fg_color=PAL["bg"])
        win.bind("<Escape>", lambda e: self.close())
        head = k.frame(win)
        head.pack(fill="x", padx=20, pady=(16, 0))
        k.clbl(head, "Ayuda", 22, "fg", True, True).pack(side="left")
        ctk.CTkButton(head, text="Cerrar", width=70, height=30, corner_radius=9, font=k.font(12), fg_color=PAL["card2"], hover_color=PAL["border"],
                      text_color=PAL["fg"], command=self.close).pack(side="right")
        self.here = k.frame(win)
        self.here.pack(fill="x", padx=20, pady=(12, 0))
        self.paint_here()
        k.clbl(win, "PREGUNTAS FRECUENTES", 10, "dim", True).pack(anchor="w", padx=20, pady=(16, 4))
        self.entry = ctk.CTkEntry(win, placeholder_text="Busca: runas, partida, PL, no veo datos…", height=34, font=k.font(12), corner_radius=10)
        self.entry.pack(fill="x", padx=20)
        self.entry.bind("<KeyRelease>", lambda e: self.paint_list())
        self.scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        self.paint_list()
        win.after(150, lambda: self.entry.focus_set())

    def close(self):
        if self.alive():
            self.win.destroy()
        self.win = None

    # ---- esta pantalla ----
    def refresh_page(self, key):
        """Tras «Enséñamelo»: la tarjeta de arriba pasa a describir la pantalla a la que se acaba de ir."""
        self.page_key = key
        if self.alive():
            self.paint_here()

    def paint_here(self):
        k = self.k
        for w in self.here.winfo_children():
            w.destroy()
        info = ayuda.page_help(self.page_key) if self.page_key else None
        if not info:
            return
        name, what, when, src = info
        card = ctk.CTkFrame(self.here, fg_color=PAL["card"], corner_radius=14, border_width=1, border_color=PAL["edge"])
        card.pack(fill="x")
        inner = k.frame(card)
        inner.pack(fill="x", padx=14, pady=12)
        k.clbl(inner, "ESTA PANTALLA", 9, "dim", True).pack(anchor="w")
        k.clbl(inner, name, 17, "fg", True, True).pack(anchor="w")
        wl = 480
        for title, text in (("Qué es", what), ("Cuándo la verás", when), ("De dónde salen los datos", src)):
            k.clbl(inner, title.upper(), 9, "info", True).pack(anchor="w", pady=(8, 0))
            k.clbl(inner, text, 11, "fg", wraplength=wl, justify="left").pack(anchor="w")

    # ---- preguntas ----
    def paint_list(self):
        k = self.k
        for w in self.scroll.winfo_children():
            w.destroy()
        found = ayuda.search(self.entry.get())
        if not found:
            k.clbl(self.scroll, "Ninguna pregunta encaja. Prueba con otra palabra (por ejemplo «runas», «partida» o «datos»).", 11, "dim", wraplength=460,
                   justify="left").pack(anchor="w", padx=8, pady=10)
            return
        for tid, question, answer, dest, _kw in found:
            card = ctk.CTkFrame(self.scroll, fg_color=PAL["card"], corner_radius=12)
            card.pack(fill="x", padx=4, pady=3)
            body = k.frame(card)
            opened = tid == self.open_id
            head = ctk.CTkButton(card, text=("▾  " if opened else "▸  ") + question, anchor="w", height=36, corner_radius=12, font=k.font(12, True), fg_color="transparent",
                                 hover_color=PAL["card2"], text_color=PAL["fg"], command=lambda t=tid: self.toggle(t))
            head.pack(fill="x")
            if opened:
                body.pack(fill="x", padx=14, pady=(0, 10))
                k.clbl(body, answer, 11, "fg", wraplength=470, justify="left").pack(anchor="w")
                label = "Enséñamelo: abrir Ajustes ›" if dest == "ajustes" else f"Enséñamelo: ir a {ayuda.PAGES[dest][0]} ›"
                ctk.CTkButton(body, text=label, height=30, corner_radius=9, font=k.font(11, True), fg_color=k.acc, text_color=PAL["bg"], hover_color=k.acc,
                              command=lambda d=dest: self.go(d)).pack(anchor="w", pady=(8, 0))

    def toggle(self, tid):
        self.open_id = None if self.open_id == tid else tid
        self.paint_list()

    def go(self, dest):
        """Lleva a la pantalla de la pregunta y deja la ayuda abierta aparte, por si quieres seguir leyendo."""
        try:
            self.gui.help_go(dest)
        except Exception:
            pass
