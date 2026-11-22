"""Ventana de permiso para la cuenta anónima de instalaciones (ver stats.py). Aparece al principio y, si se responde «Ahora no», como mucho dos veces más (una semana entre una y otra); solo si hay servidor configurado. Siempre hay «No volver a preguntar»."""
import customtkinter as ctk

import lol_advisor as core
import stats
from ui_kit import PAL

TEXTO = ("Si activas esto, LOL-E avisa una vez al día, de forma anónima, de que está instalada. Con ese aviso sé cuánta gente la usa, si las novedades llegan bien y desde qué zona "
         "aproximada (por ejemplo, la comunidad autónoma). Es lo que me ayuda a decidir en qué seguir mejorándola. Es gratis y opcional: LOL-E funciona exactamente igual si dices que no.")
SE_ENVIA = "Se envía: un número aleatorio de esta instalación y la versión de LOL-E. Nada más."
NO_SE_ENVIA = ("No se envía: tu nombre, tu cuenta de LoL, tus partidas, tus ajustes ni nada de tu ordenador. Tu dirección IP no se guarda: el servidor solo deduce la "
               "zona aproximada de la conexión y la descarta.")
CAMBIAR = "Puedes cambiarlo cuando quieras en Ajustes › Privacidad; al apagarlo se borra el registro de esta instalación."
OTRA_VEZ = "Si ahora no, te lo volveré a preguntar como mucho {n} vez(es) más, con una semana de por medio. Con «No volver a preguntar» no te molesto más."


class ConsentWindow:
    """`ui` es la interfaz principal; `on_done("yes" | "later" | "never")` se llama con la decisión. Cerrar la ventana equivale a «Ahora no».
    `last`: es la última vez que se pregunta (entonces «Ahora no» y cerrar equivalen a no)."""

    def __init__(self, ui, on_done, last=False):
        self.ui, self.on_done, self.decided = ui, on_done, False
        k = ui.kit
        w = ctk.CTkToplevel(ui.root)
        self.w = w
        w.title("LOL-E · Una pregunta")
        w.configure(fg_color=PAL["bg"])
        w.resizable(False, False)
        sc = ui.win_scale()
        W, H = 540, 530
        try:
            x = ui.root.winfo_rootx() + max(0, (ui.root.winfo_width() - int(W * sc)) // 2)
            y = ui.root.winfo_rooty() + 50
            w.geometry(f"{int(W * sc)}x{int(H * sc)}+{x}+{y}")
        except Exception:
            w.geometry(f"{W}x{H}")
        w.transient(ui.root)
        w.protocol("WM_DELETE_WINDOW", lambda: self.decide("later"))
        ctk.CTkLabel(w, text="¿Me ayudas a mejorar LOL-E?", font=k.font(18, True, True), text_color=PAL["fg"], anchor="w",
                     wraplength=int(476 * sc), justify="left").pack(fill="x", padx=24, pady=(20, 8))
        pie = CAMBIAR if last else CAMBIAR + " " + OTRA_VEZ.format(n=max(0, stats.MAX_ASKS - int(ui.conf.get("stats_asked") or 1)))
        for txt, col in ((TEXTO, "fg"), (SE_ENVIA, "fg"), (NO_SE_ENVIA, "fg"), (pie, "dim")):
            ctk.CTkLabel(w, text=txt, font=k.font(12), text_color=PAL[col], anchor="w", wraplength=int(476 * sc), justify="left").pack(fill="x", padx=24, pady=(0, 8))
        link = ctk.CTkButton(w, text="Ver exactamente qué se envía", font=k.font(11), fg_color="transparent", text_color=k.acc, hover_color=PAL["card2"],
                             width=0, anchor="w", command=self.show_payload)
        link.pack(anchor="w", padx=18, pady=(0, 6))
        self.payload_lbl = ctk.CTkLabel(w, text="", font=k.font(11), text_color=PAL["dim"], anchor="w", justify="left")
        self.payload_lbl.pack(fill="x", padx=24)
        bottom = ctk.CTkFrame(w, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=24, pady=(8, 16))
        ctk.CTkButton(bottom, text="No volver a preguntar", font=k.font(11), fg_color="transparent", text_color=PAL["dim"], hover_color=PAL["card2"], width=0,
                      command=lambda: self.decide("never")).pack(side="bottom", pady=(8, 0))
        row = ctk.CTkFrame(bottom, fg_color="transparent")
        row.pack(side="bottom", fill="x")
        ctk.CTkButton(row, text="Sí, ayudar", font=k.font(13, True), fg_color=k.acc, text_color=PAL["bg"], hover_color=k.acc, height=38,
                      command=lambda: self.decide("yes")).pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(row, text="No, gracias" if last else "Ahora no", font=k.font(13), fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["border"], height=38,
                      command=lambda: self.decide("never" if last else "later")).pack(side="left", expand=True, fill="x")

    def show_payload(self):
        shown = stats.describe({"stats_id": "(un número aleatorio como 3f2b…)"}, core.APP_VERSION)
        self.payload_lbl.configure(text=shown)

    def decide(self, res):
        if self.decided:
            return
        self.decided = True
        try:
            self.w.destroy()
        except Exception:
            pass
        self.on_done(res)
