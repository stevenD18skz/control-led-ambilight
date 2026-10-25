import os
from pathlib import Path

base = Path(__file__).resolve().parent.parent
pythonw = base / ".venv" / "Scripts" / "pythonw.exe"
icon = base / "assets" / "icon.ico"
desk_lnk = base.parent / "Control LED.lnk"
folder_lnk = base / "Control LED.lnk"

vbs = f'''Set ws = WScript.CreateObject("WScript.Shell")
Set s1 = ws.CreateShortcut("{desk_lnk}")
s1.TargetPath = "{pythonw}"
s1.Arguments = "src\\main.py"
s1.WorkingDirectory = "{base}"
s1.IconLocation = "{icon}, 0"
s1.Description = "Control LED - Modo Pantalla Ambilight"
s1.Save

Set s2 = ws.CreateShortcut("{folder_lnk}")
s2.TargetPath = "{pythonw}"
s2.Arguments = "src\\main.py"
s2.WorkingDirectory = "{base}"
s2.IconLocation = "{icon}, 0"
s2.Description = "Control LED - Modo Pantalla Ambilight"
s2.Save
'''

vbs_path = base / "upd.vbs"
vbs_path.write_text(vbs, encoding="utf-8")
os.system(f'cscript //nologo "{vbs_path}"')
if vbs_path.exists():
    vbs_path.unlink()
print("Shortcuts successfully updated to src\\main.py!")
