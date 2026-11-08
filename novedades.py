"""Novedades de la aplicación, estilo nota de parche. Se muestran una vez al abrir una versión nueva y se pueden volver a consultar
desde Ajustes. Para añadir una versión: pon una entrada nueva ARRIBA de NOTES (las más recientes primero).

Cada punto es (tipo, texto). Tipos: "nuevo", "mejora", "arreglo".
"""
import customtkinter as ctk

from ui_kit import PAL

TIPOS = {"nuevo": ("NUEVO", "good"), "mejora": ("MEJORA", "info"), "arreglo": ("ARREGLO", "warn")}

NOTES = [
    {"v": "1.15.1", "fecha": "8 de noviembre de 2026", "titulo": "Preparado para probar Mayhem", "items": [
        ("mejora", "En una partida de Mayhem LOL-E consulta la API en vivo cada 20 s y guarda hasta 6 muestras completas (cache/live_samples) para ver qué datos de mejoras trae."),
        ("mejora", "Si la API trae mejoras, se muestran por su nombre y categoría en Partida > Plan."),
    ]},
    {"v": "1.15.0", "fecha": "8 de noviembre de 2026", "titulo": "ARAM: Mayhem y sus mejoras", "items": [
        ("nuevo", "En ARAM: Mayhem, la pestaña Partida > Plan enseña las mejoras que más has elegido con tu campeón (con icono, nombre y categoría)."),
        ("nuevo", "En el Análisis de una partida de Mayhem, «Mejoras elegidas» muestra las de los 10 jugadores. Sin líneas: el rival de comparación es el que más daño hizo."),
        ("nuevo", "Durante la partida LOL-E consulta la API de partida en vivo de Riot para ver si trae tus mejoras y guarda lo que encuentre, para poder aprovecharlo."),
        ("mejora", "Riot no permite que las aplicaciones muestren porcentajes de victoria de mejoras, así que LOL-E no los enseña ni inventa una «mejor mejora»."),
    ]},
    {"v": "1.14.1", "fecha": "8 de noviembre de 2026", "titulo": "ARAM mostraba la build del campeón anterior", "items": [
        ("arreglo", "En ARAM (y Arena y otros modos sin línea) la pestaña Partida enseñaba el plan y la build de la partida anterior (por ejemplo Urgot teniendo Lee Sin). Ahora muestra tu campeón actual y avisa de que en ese modo no hay plan de línea."),
        ("arreglo", "Al empezar una selección nueva sin campeón marcado se descarta el plan de la partida anterior."),
    ]},
    {"v": "1.14.0", "fecha": "8 de noviembre de 2026", "titulo": "Draft de 5 completo", "items": [
        ("nuevo", "Tarjeta «Draft de 5» en Clasificatorias de 5 y Clash: la tira de bans y picks (verde tu equipo, rojo el rival), de quién es el turno y cuántas acciones faltan para el tuyo."),
        ("nuevo", "Bans dirigidos: por cada rival que aún no ha elegido, los campeones que más puede jugar, con puntaje (maestría, veces jugado y % de victorias) a la vista."),
        ("nuevo", "Línea probable de cada rival (los rivales no la traen) y, con ella, tu rival directo: ya se usa para el enfrentamiento y la build."),
        ("nuevo", "Rango medio de cada equipo, diferencia entre jugadores y cuentas sin rango; los perfiles rivales se leen primero y más rápido."),
        ("mejora", "Bloque de rango «Clasificatorias de 5» en el Asesor cuando tienes rango en esa cola."),
    ]},
    {"v": "1.13.3", "fecha": "8 de noviembre de 2026", "titulo": "Perfil completo de cada jugador", "items": [
        ("nuevo", "En «Tu equipo» y «Equipo rival», cada jugador tiene «Perfil completo»: sus rangos (Solo/Dúo, Flexible y Clasificatorias de 5), máximo de la temporada y de la anterior, últimas partidas con campeón y resultado, rendimiento (KDA, súbditos, daño y visión por minuto, duración), campeones más jugados, mayor maestría, líneas y señales (rachas, inactividad, cuenta secundaria)."),
        ("arreglo", "La vista «Lista» de recomendaciones podía fallar y quedarse vacía con ciertas escalas de pantalla. Corregido."),
    ]},
    {"v": "1.13.2", "fecha": "8 de noviembre de 2026", "titulo": "Clasificatorias de 5: tu rango y el de los rivales", "items": [
        ("nuevo", "En Clasificatorias de 5 se usa el rango de esa cola (tiene su propia escalera), tanto el tuyo como el de tus aliados y rivales."),
        ("nuevo", "Los PL de cada partida de Clasificatorias de 5 también se calculan."),
        ("mejora", "Un jugador sin rango y con casi ningún historial reciente se marca como «Sin rango ni historial» (cuentas nuevas o poco fiables)."),
    ]},
    {"v": "1.13.1", "fecha": "8 de noviembre de 2026", "titulo": "Clasificatorias de 5 (grupos de 5)", "items": [
        ("arreglo", "La cola «Clasificatorias de 5» se trataba como un modo desconocido y no daba recomendaciones, roles ni bans. Ahora funciona como la Grieta."),
        ("nuevo", "En esa cola el cliente enseña los nombres del equipo rival: LOL-E muestra de cada rival su rango, su forma reciente, los campeones que más juega y su maestría con el que elige."),
        ("arreglo", "Los bans de esa cola (que el cliente da de otra forma) ya se ven."),
    ]},
    {"v": "1.13.0", "fecha": "7 de noviembre de 2026", "titulo": "Novedades dentro de la aplicación", "items": [
        ("nuevo", "Esta ventana: al abrir una versión nueva verás qué ha cambiado. Puedes cerrarla y volver a consultarla en Ajustes → «Ver novedades»."),
    ]},
    {"v": "1.12.2", "fecha": "7 de noviembre de 2026", "titulo": "PL por partida y arreglos de la selección", "items": [
        ("nuevo", "PL ganados o perdidos en cada partida clasificatoria (Solo/Dúo y Flexible), con el rango actual y los ascensos o descensos."),
        ("arreglo", "El análisis de la partida recién jugada ya no muestra la anterior: LOL-E espera a que el cliente la liste."),
        ("arreglo", "En la selección de campeón, el panel de build recuerda la vista elegida (Más usada, Variantes o Situaciones)."),
    ]},
    {"v": "1.12.1", "fecha": "6 de noviembre de 2026", "titulo": "Hora en el historial", "items": [
        ("mejora", "Cada partida del Historial muestra su hora de inicio, para saber cuál fue antes y cuál después."),
    ]},
    {"v": "1.12.0", "fecha": "6 de noviembre de 2026", "titulo": "Retratos y nombres más claros", "items": [
        ("arreglo", "Los retratos de campeón ya no salen descentrados ni cortados en ninguna pantalla."),
        ("mejora", "«Núcleo» pasa a «Principales»; los huecos siguientes son «4.º, 5.º y 6.º objeto»."),
        ("mejora", "La ventana recuerda dónde estaba y se abre en el mismo monitor."),
        ("mejora", "Un solo nombre para limpiar filtros: «Restablecer filtros»."),
    ]},
]


def unseen(conf):
    return conf.get("notes_seen") != NOTES[0]["v"]


class NotesWindow:
    """Ventana de novedades. `ui` es la interfaz principal (para fuentes, colores y posición)."""

    def __init__(self, ui, on_close=None):
        self.ui, self.on_close = ui, on_close
        k = ui.kit
        w = ctk.CTkToplevel(ui.root)
        self.w = w
        w.title("LOL-E · Novedades")
        w.configure(fg_color=PAL["bg"])
        w.resizable(False, True)
        sc = ui.win_scale()
        W, H = 460, 560
        try:  # sobre la ventana principal, en su mismo monitor
            x = ui.root.winfo_rootx() + max(0, (ui.root.winfo_width() - int(W * sc)) // 2)
            y = ui.root.winfo_rooty() + 60
            w.geometry(f"{int(W * sc)}x{int(H * sc)}+{x}+{y}")
        except Exception:
            w.geometry(f"{W}x{H}")
        w.transient(ui.root)
        w.protocol("WM_DELETE_WINDOW", self.close)
        ctk.CTkLabel(w, text="Novedades", font=k.font(20, True, True), text_color=PAL["fg"], anchor="w").pack(fill="x", padx=20, pady=(18, 0))
        ctk.CTkLabel(w, text=f"Estás en la versión {NOTES[0]['v']}", font=k.font(11), text_color=PAL["dim"], anchor="w").pack(fill="x", padx=20, pady=(0, 8))
        body = ctk.CTkScrollableFrame(w, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8)
        for i, n in enumerate(NOTES):
            card = ctk.CTkFrame(body, fg_color=PAL["card"], corner_radius=10, border_width=1, border_color=PAL["border"])
            card.pack(fill="x", padx=8, pady=6)
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(12, 2))
            ctk.CTkLabel(head, text=f"Versión {n['v']}", font=k.font(14, True), text_color=k.acc if i == 0 else PAL["fg"]).pack(side="left")
            ctk.CTkLabel(head, text=n["fecha"], font=k.font(10), text_color=PAL["dim"]).pack(side="right")
            ctk.CTkLabel(card, text=n["titulo"], font=k.font(12, True), text_color=PAL["fg"], anchor="w", justify="left",
                         wraplength=int(380 * sc)).pack(fill="x", padx=14, pady=(0, 6))
            for tipo, texto in n["items"]:
                label, color = TIPOS[tipo]
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=3)
                ctk.CTkLabel(row, text=label, width=70, font=k.font(9, True), text_color=PAL[color], anchor="w").pack(side="left", anchor="n", pady=(2, 0))
                ctk.CTkLabel(row, text=texto, font=k.font(11), text_color=PAL["fg"], anchor="w", justify="left",
                             wraplength=int(300 * sc)).pack(side="left", fill="x", expand=True)
            ctk.CTkFrame(card, height=8, fg_color="transparent").pack()
        b = ctk.CTkButton(w, text="Entendido", font=k.font(12, True), fg_color=k.acc, text_color=PAL["bg"], hover_color=k.acc, command=self.close)
        b.pack(fill="x", padx=20, pady=14)
        try:
            w.after(150, w.lift)
        except Exception:
            pass

    def close(self):
        try:
            self.w.destroy()
        except Exception:
            pass
        if self.on_close:
            self.on_close()
