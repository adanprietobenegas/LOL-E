"""Ventana de permiso para la cuenta anónima de instalaciones (ver stats.py). Aparece una sola vez, solo si hay servidor configurado, y «No, gracias» es la opción destacada."""
import customtkinter as ctk

import lol_advisor as core
import stats
from ui_kit import PAL

TEXTO = ("LOL-E puede avisar una vez al día, de forma anónima, de que está instalada. Sirve solo para que quien la mantiene sepa cuánta gente la usa y desde qué "
         "zona aproximada (por ejemplo, la comunidad autónoma).")
SE_ENVIA = "Se envía: un número aleatorio de esta instalación y la versión de LOL-E."
NO_SE_ENVIA = ("No se envía: tu nombre, tu cuenta de LoL, tus partidas, tus ajustes ni nada de tu ordenador. Tu dirección IP no se guarda: el servidor solo deduce la "
               "zona aproximada de la conexión y la descarta.")
CAMBIAR = "Puedes cambiarlo cuando quieras en Ajustes › Privacidad; al apagarlo se borra el registro de esta instalación."


class ConsentWindow:
    """`ui` es la interfaz principal; `on_done(True|False)` se llama con la decisión (cerrar la ventana equivale a «No, gracias»)."""

    def __init__(self, ui, on_done):
        self.ui, self.on_done, self.decided = ui, on_done, False
        k = ui.kit
        w = ctk.CTkToplevel(ui.root)
        self.w = w
        w.title("LOL-E · Una pregunta")
        w.configure(fg_color=PAL["bg"])
        w.resizable(False, False)
        sc = ui.win_scale()
        W, H = 520, 440
        try:
            x = ui.root.winfo_rootx() + max(0, (ui.root.winfo_width() - int(W * sc)) // 2)
            y = ui.root.winfo_rooty() + 70
            w.geometry(f"{int(W * sc)}x{int(H * sc)}+{x}+{y}")
        except Exception:
            w.geometry(f"{W}x{H}")
        w.transient(ui.root)
        w.protocol("WM_DELETE_WINDOW", lambda: self.decide(False))
        ctk.CTkLabel(w, text="¿Ayudas a contar cuánta gente usa LOL-E?", font=k.font(18, True, True), text_color=PAL["fg"], anchor="w",
                     wraplength=int(480 * sc), justify="left").pack(fill="x", padx=24, pady=(20, 8))
        for txt, col in ((TEXTO, "fg"), (SE_ENVIA, "fg"), (NO_SE_ENVIA, "fg"), (CAMBIAR, "dim")):
            ctk.CTkLabel(w, text=txt, font=k.font(12), text_color=PAL[col], anchor="w", wraplength=int(480 * sc), justify="left").pack(fill="x", padx=24, pady=(0, 8))
        link = ctk.CTkButton(w, text="Ver exactamente qué se envía", font=k.font(11), fg_color="transparent", text_color=k.acc, hover_color=PAL["card2"],
                             width=0, anchor="w", command=self.show_payload)
        link.pack(anchor="w", padx=18, pady=(0, 6))
        self.payload_lbl = ctk.CTkLabel(w, text="", font=k.font(11), text_color=PAL["dim"], anchor="w", justify="left")
        self.payload_lbl.pack(fill="x", padx=24)
        row = ctk.CTkFrame(w, fg_color="transparent")
        row.pack(side="bottom", fill="x", padx=24, pady=(8, 20))
        ctk.CTkButton(row, text="No, gracias", font=k.font(13, True), fg_color=k.acc, text_color=PAL["bg"], hover_color=k.acc, height=38,
                      command=lambda: self.decide(False)).pack(side="left", expand=True, fill="x", padx=(0, 8))
        b = ctk.CTkButton(row, text="Sí, contar mi instalación", font=k.font(13), fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["border"], height=38,
                          command=lambda: self.decide(True))
        b.pack(side="left", expand=True, fill="x")

    def show_payload(self):
        shown = stats.describe({"stats_id": "(un número aleatorio como 3f2b…)"}, core.APP_VERSION)
        self.payload_lbl.configure(text=shown)

    def decide(self, yes):
        if self.decided:
            return
        self.decided = True
        try:
            self.w.destroy()
        except Exception:
            pass
        self.on_done(bool(yes))
