"""Construye el paquete de distribucion de LOL-E.

Requisitos (solo en el PC donde se compila): Python 3.12 con `pip install customtkinter pillow pyinstaller`
e Inno Setup 6. Resultado: release/LOL-E-<version>.zip

Uso:  python build_release.py
"""
import base64, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lol_advisor import APP_VERSION as VER  # noqa: E402

TMP = os.path.join(os.environ.get("TEMP", HERE), "lolb")  # ruta corta: Inno Setup no admite rutas de mas de 260 caracteres
REL = os.path.join(HERE, "release")
DOCS = os.path.join(HERE, "docs")
ISCC = next((p for p in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
                         r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe")
             if os.path.exists(p)), None)
USER_DATA = os.path.join(HERE, "cache")  # datos iniciales: solo campeones e iconos, nada personal


def run(cmd):
    print(">", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    subprocess.run(cmd, check=True)


def step(t):
    print(f"\n=== {t} ===")


def main():
    assert ISCC, "No encuentro Inno Setup 6 (winget install JRSoftware.InnoSetup)"
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    shutil.rmtree(REL, ignore_errors=True)
    os.makedirs(REL)

    step("1/5 Icono")
    icon = os.path.join(HERE, "assets", "icon.ico")

    step("2/5 Ejecutable (PyInstaller)")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "LOL-E",
         "--icon", icon, "--collect-all", "customtkinter", "--add-data", f"{HERE}\\assets\\icon.png;assets", "--add-data", f"{HERE}\\assets\\icon.ico;assets",
         "--add-data", f"{HERE}\\assets\\fonts;assets\\fonts", "--add-data", f"{HERE}\\assets\\claves.json;assets", "--distpath", os.path.join(TMP, "dist"),
         "--workpath", os.path.join(TMP, "work"), "--specpath", TMP, "--paths", HERE, os.path.join(HERE, "app.py")])

    step("3/5 Datos iniciales (campeones e iconos, sin datos personales)")
    seed = os.path.join(TMP, "seed_cache")
    os.makedirs(seed)
    for f in ("champions.json", "meraki.json"):
        shutil.copy2(os.path.join(USER_DATA, f), seed)
    shutil.copytree(os.path.join(USER_DATA, "icons"), os.path.join(seed, "icons"))

    step("4/5 Instalador (Inno Setup)")
    iss = os.path.join(TMP, "instalador.iss")
    defs = {"Ver": VER, "Dist": os.path.join(TMP, "dist", "LOL-E"), "Seed": seed, "Icon": icon, "Out": TMP}
    with open(iss, "w", encoding="utf-8-sig") as f:
        f.write("".join(f'#define {k} "{v}"\n' for k, v in defs.items()) + ISS)
    run([ISCC, "/Q", iss])
    setup = os.path.join(TMP, f"Instalar-LOL-E-{VER}.exe")
    assert os.path.exists(setup), "el instalador no se genero"

    step("5/5 Paquete .zip con instrucciones")
    folder = os.path.join(REL, f"LOL-E {VER}")
    os.makedirs(folder)
    shutil.copy2(setup, os.path.join(folder, f"1_Instalar-LOL-E-{VER}.exe"))
    for src, dst in (("LEEME_PRIMERO.txt", "0_LEEME_PRIMERO.txt"), ("NOTAS_DE_VERSION.txt", "3_NOTAS_DE_VERSION.txt")):
        text = open(os.path.join(DOCS, src), encoding="utf-8").read().replace("\r\n", "\n").replace("\n", "\r\n")
        with open(os.path.join(folder, dst), "w", encoding="utf-8-sig", newline="") as f:  # BOM: el Bloc de notas muestra bien los acentos
            f.write(text)
    html = open(os.path.join(DOCS, "guia.template.html"), encoding="utf-8").read()
    for key, img in (("IMG_IDLE", "idle"), ("IMG_SELECT", "select"), ("IMG_SETTINGS", "settings"), ("IMG_TEAM", "equipo"), ("IMG_MATCHUP", "matchup"), ("IMG_DATOS", "datos"), ("IMG_HIST", "historial"), ("IMG_BUILD", "build"), ("IMG_REP", "repertorio")):
        b64 = base64.b64encode(open(os.path.join(DOCS, "img", f"{img}.png"), "rb").read()).decode()
        html = html.replace("{{" + key + "}}", f"data:image/png;base64,{b64}")
    html = html.replace("{{VER}}", VER)
    assert "{{" not in html
    open(os.path.join(folder, "2_GUIA_VISUAL.html"), "w", encoding="utf-8").write(html.replace("{{VER}}", VER))

    zpath = os.path.join(REL, f"LOL-E-{VER}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for fn in sorted(os.listdir(folder)):
            z.write(os.path.join(folder, fn), os.path.join(os.path.basename(folder), fn))
    # archivo de version para las actualizaciones automaticas (se publica junto al instalador)
    import hashlib, json
    sha = hashlib.sha256(open(setup, "rb").read()).hexdigest()
    base = os.environ.get("LOLE_UPDATE_BASE", "https://github.com/adanprietobenegas/LOL-E/releases/latest/download/")
    shutil.copy2(setup, os.path.join(REL, f"Instalar-LOL-E-{VER}.exe"))
    json.dump({"version": VER, "url": f"{base}Instalar-LOL-E-{VER}.exe", "sha256": sha,
               "notes": "Consulta las notas de versión incluidas en el paquete."}, open(os.path.join(REL, "latest.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(f"\nLISTO: {zpath}  ({os.path.getsize(zpath) / 1e6:.1f} MB)\nPara actualizaciones: publica release/latest.json y release/Instalar-LOL-E-{VER}.exe juntos")


ISS = r"""
#define AppName "LOL-E"
[Setup]
AppId={{B3A94D1E-52C7-4F08-8E6B-1D7A0C9F4E25}
AppName={#AppName}
AppVersion={#Ver}
AppPublisher=LOL-E
DefaultDirName={autopf}\LOL-E
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableWelcomePage=yes
PrivilegesRequired=lowest
OutputDir={#Out}
OutputBaseFilename=Instalar-LOL-E-{#Ver}
SetupIconFile={#Icon}
UninstallDisplayIcon={app}\LOL-E.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#Dist}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "{#Seed}\*"; DestDir: "{app}\seed_cache"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\LOL-E"; Filename: "{app}\LOL-E.exe"
Name: "{autodesktop}\LOL-E"; Filename: "{app}\LOL-E.exe"

[Run]
Filename: "{app}\LOL-E.exe"; Description: "Abrir LOL-E ahora"; Flags: nowait postinstall skipifsilent
Filename: "{app}\LOL-E.exe"; Flags: nowait; Check: UpdateMode

[Code]
function UpdateMode: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox('¿Quieres borrar también tus datos y ajustes de LOL-E?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\LOL-E'), True, True, True);
end;
"""

if __name__ == "__main__":
    main()
