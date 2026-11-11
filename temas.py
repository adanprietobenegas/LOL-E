"""Temas de la interfaz: 6 de color, 5 «looks» con personalidad propia y 3 estilos de tarjeta, combinables.

Hay dos familias:
· TEMAS DE COLOR (Abisal, Neón medianoche, Brasa, Bosque, Cloud Dancer, más el Predeterminado): cambian solo la paleta. Se combinan con cualquiera
  de los 3 ESTILOS (Plano, Brutal, Cristal), que cambian la forma (radio de las esquinas, borde, sombra) en toda la aplicación.
· LOOKS (Terminal, Papel, Blueprint, Hextech, Arcade): no son solo colores. Cada uno trae su paleta, su tipografía, su forma, el tipo de borde y su
  manera de titular las tarjetas. Traen su propio estilo, así que el selector de estilo no se aplica a ellos.

Salieron de una auditoría de color (contrastes WCAG calculados, daltonismo simulado) y de estilos (viabilidad en Tk): los colores semánticos
(victoria, derrota, aliado, rival, aviso) se mantienen distinguibles en todos, y la victoria y la derrota llevan además forma y signo. Estilos
descartados: neumorfismo (contraste ≈1,1:1, incumple WCAG 1.4.11). «Cristal» es una aproximación sin desenfoque real porque Tk no lo permite.
Ver docs/rediseno/PROPUESTA_REDISENO.md.
"""
import customtkinter as ctk

import ui_kit

DEFAULT_THEME, DEFAULT_STYLE = "Predeterminado", "Plano"

# nombre -> {modo: {rol: color}}. Roles: bg, s1 (tarjeta), s2 (panel interior), text, text2, acento_consulta, acento_vivo, positivo, negativo, aliado, rival, aviso
COLORES = {'Abisal': {'oscuro': {'bg': '#0C1220',
                       's1': '#141C30',
                       's2': '#1D2740',
                       'text': '#EAF0FA',
                       'text2': '#9AA9C8',
                       'acento_consulta': '#5CC8E8',
                       'acento_vivo': '#B58CFF',
                       'positivo': '#6FF0CC',
                       'negativo': '#FF5C6C',
                       'aliado': '#4DA3FF',
                       'rival': '#FFA13D',
                       'aviso': '#F2D04A'},
            'claro': {'bg': '#F2F5FA',
                      's1': '#E3E9F3',
                      's2': '#D3DCEA',
                      'text': '#101A30',
                      'text2': '#455471',
                      'acento_consulta': '#0D6783',
                      'acento_vivo': '#6B3FD0',
                      'positivo': '#006A5D',
                      'negativo': '#991B2F',
                      'aliado': '#1E5DBB',
                      'rival': '#944A00',
                      'aviso': '#7A5C00'}},
 'Neón medianoche': {'oscuro': {'bg': '#0A0C14',
                                's1': '#12151F',
                                's2': '#1B1F2D',
                                'text': '#F0F2FA',
                                'text2': '#A0A7C0',
                                'acento_consulta': '#8C7CFF',
                                'acento_vivo': '#C6F432',
                                'positivo': '#6FF0CC',
                                'negativo': '#FF5C6C',
                                'aliado': '#4DA3FF',
                                'rival': '#FFA13D',
                                'aviso': '#F2D04A'},
                     'claro': {'bg': '#F5F6FA',
                               's1': '#E7E9F1',
                               's2': '#D8DBE7',
                               'text': '#12142A',
                               'text2': '#4C5170',
                               'acento_consulta': '#5A3FD0',
                               'acento_vivo': '#456B00',
                               'positivo': '#006A5D',
                               'negativo': '#991B2F',
                               'aliado': '#1E5DBB',
                               'rival': '#944A00',
                               'aviso': '#7A5C00'}},
 'Brasa': {'oscuro': {'bg': '#15110F',
                      's1': '#211B18',
                      's2': '#2D2521',
                      'text': '#F5EEE8',
                      'text2': '#B9A99C',
                      'acento_consulta': '#4FC3D9',
                      'acento_vivo': '#B8F040',
                      'positivo': '#6FF0CC',
                      'negativo': '#FF5C6C',
                      'aliado': '#4DA3FF',
                      'rival': '#FFA13D',
                      'aviso': '#F2D04A'},
           'claro': {'bg': '#F8F3EE',
                     's1': '#EDE5DD',
                     's2': '#E0D5CA',
                     'text': '#241A14',
                     'text2': '#5F4F43',
                     'acento_consulta': '#0D6677',
                     'acento_vivo': '#486500',
                     'positivo': '#006A5D',
                     'negativo': '#991B2F',
                     'aliado': '#1E5BB6',
                     'rival': '#8E4700',
                     'aviso': '#755800'}},
 'Bosque': {'oscuro': {'bg': '#0C1813',
                       's1': '#13241C',
                       's2': '#1B3127',
                       'text': '#EAF4EE',
                       'text2': '#9BB8A8',
                       'acento_consulta': '#C3A8FF',
                       'acento_vivo': '#D4F55A',
                       'positivo': '#6FF0CC',
                       'negativo': '#FF5C6C',
                       'aliado': '#4DA3FF',
                       'rival': '#FFA13D',
                       'aviso': '#F2D04A'},
            'claro': {'bg': '#F2F7F3',
                      's1': '#E2ECE5',
                      's2': '#D1E0D6',
                      'text': '#10281E',
                      'text2': '#3D5C4C',
                      'acento_consulta': '#6A44C0',
                      'acento_vivo': '#4B6A00',
                      'positivo': '#006A5D',
                      'negativo': '#991B2F',
                      'aliado': '#1E5DBB',
                      'rival': '#994C00',
                      'aviso': '#7A5C00'}},
 'Cloud Dancer': {'oscuro': {'bg': '#101823',
                             's1': '#18283A',
                             's2': '#203349',
                             'text': '#F0EEE9',
                             'text2': '#A0B0C4',
                             'acento_consulta': '#7FA8D3',
                             'acento_vivo': '#B58CFF',
                             'positivo': '#6FF0CC',
                             'negativo': '#FF7482',
                             'aliado': '#4DA3FF',
                             'rival': '#FFA13D',
                             'aviso': '#F2D04A'},
                  'claro': {'bg': '#F0EEE9',
                            's1': '#E6E3DC',
                            's2': '#D8D4CB',
                            'text': '#15233A',
                            'text2': '#484F5C',
                            'acento_consulta': '#0F4C81',
                            'acento_vivo': '#683BCF',
                            'positivo': '#006559',
                            'negativo': '#991B2F',
                            'aliado': '#1D58B2',
                            'rival': '#8E4700',
                            'aviso': '#755800'}}}

LOOKS = {'Terminal': {'oscuro': {'bg': '#050A06',
                         's1': '#0B140D',
                         's2': '#12201A',
                         'text': '#C8F5D0',
                         'text2': '#86BA92',
                         'acento_consulta': '#39FF88',
                         'acento_vivo': '#FFB000',
                         'positivo': '#6FF0CC',
                         'negativo': '#FF5C6C',
                         'aliado': '#4DA3FF',
                         'rival': '#FFA13D',
                         'aviso': '#F2D04A'},
              'claro': {'bg': '#EDF3E6',
                        's1': '#E0EAD7',
                        's2': '#D0DEC4',
                        'text': '#0E2A14',
                        'text2': '#35563C',
                        'acento_consulta': '#0B6B2E',
                        'acento_vivo': '#8A5A00',
                        'positivo': '#006A5D',
                        'negativo': '#991B2F',
                        'aliado': '#1B54AB',
                        'rival': '#944A00',
                        'aviso': '#6E5300'}},
 'Papel': {'claro': {'bg': '#F4EFE4',
                     's1': '#FBF8F1',
                     's2': '#EAE3D3',
                     'text': '#1E1B16',
                     'text2': '#5A5346',
                     'acento_consulta': '#8A1C1C',
                     'acento_vivo': '#1F4E79',
                     'positivo': '#006A5D',
                     'negativo': '#991B2F',
                     'aliado': '#1E5DBB',
                     'rival': '#944A00',
                     'aviso': '#7A5C00'},
           'oscuro': {'bg': '#1B1712',
                      's1': '#241F18',
                      's2': '#2E271E',
                      'text': '#EDE5D2',
                      'text2': '#B8AC93',
                      'acento_consulta': '#E0A96B',
                      'acento_vivo': '#8FB8E0',
                      'positivo': '#6FF0CC',
                      'negativo': '#FF5C6C',
                      'aliado': '#4DA3FF',
                      'rival': '#FFA13D',
                      'aviso': '#F2D04A'}},
 'Blueprint': {'oscuro': {'bg': '#0A2540',
                          's1': '#103559',
                          's2': '#18466F',
                          'text': '#EAF4FF',
                          'text2': '#A9C6E6',
                          'acento_consulta': '#7DD3FC',
                          'acento_vivo': '#FFD166',
                          'positivo': '#6FF0CC',
                          'negativo': '#FF9AA3',
                          'aliado': '#7DBAFF',
                          'rival': '#FFA13D',
                          'aviso': '#F2D04A'},
               'claro': {'bg': '#EAF2FA',
                         's1': '#DCE9F6',
                         's2': '#CBDDF0',
                         'text': '#0B2A4A',
                         'text2': '#3F5F82',
                         'acento_consulta': '#0B5CAD',
                         'acento_vivo': '#8A5A00',
                         'positivo': '#006A5D',
                         'negativo': '#991B2F',
                         'aliado': '#1E5DBB',
                         'rival': '#944A00',
                         'aviso': '#7A5C00'}},
 'Hextech': {'oscuro': {'bg': '#010A13',
                        's1': '#0A1428',
                        's2': '#122240',
                        'text': '#F0E6D2',
                        'text2': '#A9A395',
                        'acento_consulta': '#C8AA6E',
                        'acento_vivo': '#0AC8B9',
                        'positivo': '#6FF0CC',
                        'negativo': '#FF5C6C',
                        'aliado': '#4DA3FF',
                        'rival': '#FFA13D',
                        'aviso': '#F2D04A'},
             'claro': {'bg': '#F3EDE0',
                       's1': '#EAE2D0',
                       's2': '#E3DAC4',
                       'text': '#1A1408',
                       'text2': '#5C5238',
                       'acento_consulta': '#7A5C14',
                       'acento_vivo': '#00605A',
                       'positivo': '#00594F',
                       'negativo': '#991B2F',
                       'aliado': '#174F9C',
                       'rival': '#7C3E00',
                       'aviso': '#655000'}},
 'Arcade': {'oscuro': {'bg': '#14082B',
                       's1': '#1F0F42',
                       's2': '#2C1A5A',
                       'text': '#FFF3FF',
                       'text2': '#CDBBF2',
                       'acento_consulta': '#FF5CC0',
                       'acento_vivo': '#22E6FF',
                       'positivo': '#6FF0CC',
                       'negativo': '#FF5C6C',
                       'aliado': '#4DA3FF',
                       'rival': '#FFA13D',
                       'aviso': '#F2D04A'},
            'claro': {'bg': '#FFF4D6',
                      's1': '#FBE8B8',
                      's2': '#F4DA98',
                      'text': '#2A0F4A',
                      'text2': '#5C3C80',
                      'acento_consulta': '#B3005F',
                      'acento_vivo': '#006E85',
                      'positivo': '#006A5D',
                      'negativo': '#991B2F',
                      'aliado': '#1E5DBB',
                      'rival': '#944A00',
                      'aviso': '#7A5C00'}},
 'Neón Tokio': {'oscuro': {'bg': '#08060F',
                           's1': '#110C1F',
                           's2': '#1B1330',
                           'text': '#F4EEFF',
                           'text2': '#B7A8D6',
                           'acento_consulta': '#FF2E97',
                           'acento_vivo': '#00F0FF',
                           'positivo': '#6FF0CC',
                           'negativo': '#FF5C6C',
                           'aliado': '#4DA3FF',
                           'rival': '#FFA13D',
                           'aviso': '#F2D04A'},
                'claro': {'bg': '#FBF4FF',
                          's1': '#F1E6FA',
                          's2': '#E6D6F4',
                          'text': '#220F3A',
                          'text2': '#5A3F7C',
                          'acento_consulta': '#B0006B',
                          'acento_vivo': '#00677A',
                          'positivo': '#006A5D',
                          'negativo': '#991B2F',
                          'aliado': '#1E5DBB',
                          'rival': '#944A00',
                          'aviso': '#7A5C00'}},
 'Océano': {'oscuro': {'bg': '#06202A',
                       's1': '#0B2F3D',
                       's2': '#124356',
                       'text': '#E6F7FA',
                       'text2': '#9CC8D2',
                       'acento_consulta': '#2EC4B6',
                       'acento_vivo': '#FF8C69',
                       'positivo': '#6FF0CC',
                       'negativo': '#FF9AA3',
                       'aliado': '#7DBAFF',
                       'rival': '#FFA13D',
                       'aviso': '#F2D04A'},
            'claro': {'bg': '#EAF7F7',
                      's1': '#DCEFF0',
                      's2': '#C9E3E6',
                      'text': '#0A2E38',
                      'text2': '#3C6670',
                      'acento_consulta': '#00706A',
                      'acento_vivo': '#9A3F1C',
                      'positivo': '#006A5D',
                      'negativo': '#991B2F',
                      'aliado': '#1E5DBB',
                      'rival': '#944A00',
                      'aviso': '#7A5C00'}}}
# Forma, tipografía y detalles de cada look. borde: «acento», «texto», «edge» o «claro»; titulo: «barra» (la de siempre), «regla» (subrayado grueso)
# o «corchetes» ([ TÍTULO ]); doble: segundo marco fino por dentro (aspecto de plano o de filigrana).
FORMA_LOOKS = {
    "Terminal":  {"radio": 0.0,  "bw": 1, "sombra": (0, 0), "borde": "acento", "filo": False, "sombra_color": "shadow", "doble": False, "titulo": "corchetes",
                  "fuentes": ("Consolas", "Consolas"), "nota": "Pantalla de terminal: verde fosforito, todo en monoespaciada y esquinas rectas."},
    "Papel":     {"radio": 0.15, "bw": 1, "sombra": (0, 0), "borde": "texto",  "filo": False, "sombra_color": "shadow", "doble": False, "titulo": "regla",
                  "fuentes": ("Georgia", "Georgia"), "nota": "Periódico: serif, papel crema, filetes finos y títulos subrayados."},
    "Blueprint": {"radio": 0.0,  "bw": 1, "sombra": (0, 0), "borde": "acento", "filo": False, "sombra_color": "shadow", "doble": True, "titulo": "barra",
                  "fuentes": ("Bahnschrift", "Bahnschrift"), "nota": "Plano técnico: azul de delineante, doble línea fina y tipografía de rotulación."},
    "Hextech":   {"radio": 0.4,  "bw": 1, "sombra": (0, 3), "borde": "acento", "filo": True,  "sombra_color": "shadow", "doble": True, "titulo": "regla",
                  "fuentes": ("Chakra Petch", "Segoe UI"), "nota": "Arcano: oro y azul profundo, doble marco dorado y filo de luz."},
    "Arcade":    {"radio": 0.35, "bw": 3, "sombra": (5, 5), "borde": "texto",  "filo": False, "sombra_color": "acento", "doble": False, "titulo": "barra",
                  "fuentes": ("Chakra Petch", "Segoe UI"), "nota": "Recreativa: morado y neón, bordes gruesos y sombra dura de color."},
    "Neón Tokio": {"radio": 0.5, "bw": 2, "sombra": (0, 0), "borde": "acento", "filo": False, "sombra_color": "shadow", "doble": True, "titulo": "regla",
                  "fuentes": ("Bahnschrift", "Segoe UI"), "nota": "Neón: noche de ciudad, doble borde luminoso rosa y cian."},
    "Océano":    {"radio": 1.7,  "bw": 1, "sombra": (0, 4), "borde": "claro",  "filo": True,  "sombra_color": "shadow", "doble": False, "titulo": "barra",
                  "fuentes": (None, "Segoe UI Semilight"), "nota": "Marea: verdes azulados, esquinas muy redondas y superficies suaves."},
}
NOMBRES = [DEFAULT_THEME] + list(COLORES) + list(LOOKS)
LOOKS_NOMBRES = list(LOOKS)

# Tokens de forma de los 3 estilos. radio: factor que se aplica a TODAS las esquinas redondeadas; bw: grosor del borde de las tarjetas;
# sombra: (dx, dy) en px; filo: línea clara arriba (Cristal).
ESTILOS = {
    "Plano":   {"radio": 1.0,  "bw": 1, "sombra": (0, 3), "borde": "edge",  "filo": False, "sombra_color": "shadow", "doble": False, "titulo": "barra", "fuentes": (None, None),
                "nota": "Tarjetas redondeadas con sombra suave: el aspecto de siempre."},
    "Brutal":  {"radio": 0.25, "bw": 2, "sombra": (4, 4), "borde": "texto", "filo": False, "sombra_color": "acento", "doble": False, "titulo": "barra", "fuentes": (None, None),
                "nota": "Esquinas casi rectas, borde grueso y sombra dura desplazada."},
    "Cristal": {"radio": 1.3,  "bw": 1, "sombra": (0, 2), "borde": "claro", "filo": True,  "sombra_color": "shadow", "doble": False, "titulo": "barra", "fuentes": (None, None),
                "nota": "Superficies más claras, bordes luminosos y filo de luz arriba (aproximación: sin desenfoque real)."},
}
ESTILOS_NOMBRES = list(ESTILOS)

_DEFAULT_PAL = {k: tuple(v) for k, v in ui_kit.PAL.items()}
_DEFAULT_FONTS = (ui_kit.DISPLAY, ui_kit.BODY)
_state = {"style": DEFAULT_STYLE, "theme": DEFAULT_THEME, "patched": False, "scale": 1.0, "forma": ESTILOS[DEFAULT_STYLE]}


def _mix(a, b, t):
    return ui_kit.mix(a, b, t)


def _pal_from(m, dark):
    """Paleta de la aplicación (las claves de ui_kit.PAL) a partir de los roles de un tema, en un modo."""
    bg, s1, s2, tx, t2 = m["bg"], m["s1"], m["s2"], m["text"], m["text2"]
    return {"bg": bg, "card": s1, "card2": s2, "well": _mix(bg, s1, .5), "shadow": _mix(bg, "#000000", .45 if dark else .12),
            "edge": _mix(s2, tx, .2), "border": _mix(s2, tx, .15), "fg": tx, "dim": t2, "good": m["positivo"], "bad": m["negativo"],
            "info": m["aliado"], "warn": m["aviso"], "chip": _mix(s2, tx, .08)}


def _patch_radios():
    """Una sola vez: los widgets de CustomTkinter multiplican su corner_radius por el factor del estilo (así el estilo llega a todas las pantallas
    sin tocar cada llamada)."""
    if _state["patched"]:
        return
    for cls in (ctk.CTkFrame, ctk.CTkButton, ctk.CTkLabel, ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkSegmentedButton, ctk.CTkTextbox):
        orig = cls.__init__

        def make(orig):
            def init(self, *a, **kw):
                f = _state["scale"]
                r = kw.get("corner_radius")
                if f != 1.0 and isinstance(r, (int, float)) and not isinstance(r, bool):
                    kw["corner_radius"] = max(0, round(r * f))
                orig(self, *a, **kw)
            return init
        cls.__init__ = make(orig)
    _state["patched"] = True


def apply(conf):
    """Aplica el tema y el estilo guardados en `conf` (claves color_theme y style). Llamar antes de crear la interfaz y al cambiarlos."""
    name = conf.get("color_theme", DEFAULT_THEME)
    pal = ui_kit.PAL
    st_name = conf.get("style", DEFAULT_STYLE)
    st_name = st_name if st_name in ESTILOS else DEFAULT_STYLE
    base, acc = {k: tuple(v) for k, v in _DEFAULT_PAL.items()}, None
    src = COLORES.get(name) or LOOKS.get(name)
    if src:
        d, l = _pal_from(src["oscuro"], True), _pal_from(src["claro"], False)
        base = {k: (l[k], d[k]) for k in d}
        acc = (src["claro"]["acento_consulta"], src["oscuro"]["acento_consulta"])
    forma = dict(FORMA_LOOKS[name]) if name in LOOKS else dict(ESTILOS[st_name])
    if forma["filo"] and name not in LOOKS:   # Cristal: tarjetas más claras que el fondo (en claro hacia el blanco; en oscuro, un poco de luz)
        c = base["card"]
        base["card"] = (_mix(c[0], "#ffffff", .55), _mix(c[1], base["fg"][1], .07))
    for k, v in base.items():
        pal[k] = v
    if acc:
        ui_kit.ACCENTS["Tema"] = acc
    else:
        ui_kit.ACCENTS.pop("Tema", None)
    f_disp, f_body = forma.get("fuentes") or (None, None)
    ui_kit.DISPLAY, ui_kit.BODY = f_disp or _DEFAULT_FONTS[0], f_body or _DEFAULT_FONTS[1]
    _state.update(style=st_name, theme=name, forma=forma, scale=forma["radio"])
    _patch_radios()


def style():
    """Tokens de forma vigentes (los del estilo elegido, o los del look si el tema es un look)."""
    return _state["forma"]


def is_look(name=None):
    return (name or _state["theme"]) in LOOKS


def accent_for(theme):
    """Nombre del acento que corresponde a un tema al elegirlo: el propio del tema, o el dorado de siempre en el predeterminado."""
    return "Tema" if theme in COLORES or theme in LOOKS else "Dorado"
