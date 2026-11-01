#!/usr/bin/env python3
"""Prueba automática: los «Ajustes avanzados» se guardan al cerrar la ventana y vuelven al abrirla.

Uso:  python prueba_ajustes.py <orden del programa...>
  Linux:   escribe de verdad con xdotool y cierra con la X (wmctrl -c, necesita un gestor de ventanas).
  Windows: cambia los valores por la vía de prueba MCS_PRUEBA_PONER y cierra con WM_CLOSE (lo mismo que la X).
Sale con 0 si todo vuelve igual. No toca nada fuera de la carpeta de configuración que se le da (HOME/APPDATA)."""
import json, os, subprocess, sys, time, threading, re, tempfile
from pathlib import Path

ORDEN = sys.argv[1:] or [sys.executable, "-u", str(Path(__file__).with_name("buscar_tinta_papiro.py"))]
WIN = os.name == "nt"
PONER = WIN or os.environ.get("MCS_PRUEBA_MODO") == "poner"   # sin teclear: como en Windows
TITULO = "MCSerDeLuz - Buscar tinta en el papiro (sin IA)"
CAMBIOS = {"percentil": "99", "tam_min": "20", "dpi": "150", "limite_mb": "120", "z_umbral": "3.5",
           "delante": "13,14,15", "max_candidatos": "abc", "sin_descargas": True, "rehacer": True, "sin_crujido": True}
SALIDA = str(Path(tempfile.gettempdir()) / "mcs-prueba-resultados")
CAMBIOS["salida"] = SALIDA
# "abc" no vale: tiene que volver tal cual escrito, y en el JSON tiene que quedar el último valor bueno (0)
ESPERADO = dict(CAMBIOS)


def lanzar(env_extra):
    env = dict(os.environ, MCS_PRUEBA_VENTANA="1", PYTHONIOENCODING="utf-8", **env_extra)
    p = subprocess.Popen(ORDEN, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    lineas = []

    def leer():
        for b in p.stdout:
            s = b.decode("utf-8", "replace").rstrip()
            lineas.append(s)
            print("   | " + s[:300], flush=True)
    threading.Thread(target=leer, daemon=True).start()
    return p, lineas


def esperar(lineas, patron, seg=90):
    t = time.time()
    while time.time() - t < seg:
        for s in list(lineas):
            if re.search(patron, s):
                return s
        time.sleep(0.2)
    raise SystemExit(f"FALLO: no apareció «{patron}» en {seg} s")


def ultima(lineas, patron):
    m = [s for s in lineas if re.search(patron, s)]
    return m[-1] if m else None


def json_de(s):
    return json.loads(s[s.index("{"):])


def cerrar_con_x():
    if WIN:
        import ctypes
        u = ctypes.windll.user32
        h = u.FindWindowW(None, TITULO)
        if not h:
            raise SystemExit("FALLO: no encuentro la ventana para cerrarla")
        u.PostMessageW(h, 0x0010, 0, 0)        # WM_CLOSE = pulsar la X
    else:
        subprocess.run(["wmctrl", "-c", TITULO], check=True)


def xdo(*a):
    subprocess.run(["xdotool", *map(str, a)], check=True)


def main():
    if os.environ.get("MCS_PRUEBA_GUARDADO_AQUI"):
        print("archivo de ajustes:", os.environ["MCS_PRUEBA_GUARDADO_AQUI"])
    # ---- 1ª sesión: cambiar valores y cerrar con la X
    extra = {"MCS_PRUEBA_PONER": json.dumps(dict(CAMBIOS, panel=True))} if PONER else {}
    p, L = lanzar(extra)
    esperar(L, r"PRUEBA valores")
    if PONER:
        esperar(L, r"PRUEBA puesto")
    else:
        esperar(L, r"PRUEBA panel cerrado")
        pos = json_de(ultima(L, r"PRUEBA panel cerrado"))
        xdo("mousemove", *pos["boton_ajustes"], "click", 1)
        esperar(L, r"PRUEBA panel abierto")
        pos = json_de(ultima(L, r"PRUEBA panel abierto"))
        for k, v in CAMBIOS.items():
            if isinstance(v, bool):
                xdo("mousemove", *pos[k], "click", 1)
            else:
                xdo("mousemove", *pos[k], "click", "--repeat", 3, "--delay", 80, 1)
                time.sleep(0.2)
                xdo("type", "--delay", 30, v)
            time.sleep(0.3)
    time.sleep(0.2)                    # sin esperar al guardado diferido: se cierra enseguida
    cerrar_con_x()
    try:
        p.wait(30)
    except subprocess.TimeoutExpired:
        p.kill()
        raise SystemExit("FALLO: la ventana no se cerró con la X")
    time.sleep(0.5)
    # ---- 2ª sesión: ¿han vuelto?
    p, L = lanzar({})
    s = esperar(L, r"PRUEBA valores")
    vals = json_de(s)
    time.sleep(0.5)
    cerrar_con_x()
    try:
        p.wait(30)
    except subprocess.TimeoutExpired:
        p.kill()
    malos = []
    for k, v in ESPERADO.items():
        got = vals.get("textos", {}).get(k)
        ok = (bool(got) == v) if isinstance(v, bool) else (str(got).replace(",", ".") == v
                                                            or _num(got) == _num(v) or (k == "salida" and
                                                            os.path.normcase(str(got)) == os.path.normcase(v)))
        print(f"   {k:<14} esperado {v!r:<12} recuperado {got!r}  {'OK' if ok else 'MAL'}")
        if not ok:
            malos.append(k)
    print(f"   panel abierto al volver: {vals.get('panel_abierto')}")
    if not vals.get("panel_abierto"):
        malos.append("panel_abierto")
    arch = Path(vals["archivo"])
    d = json.loads(arch.read_text(encoding="utf-8"))
    print(f"   JSON {arch}: percentil {d.get('percentil')}, tam_min {d.get('tam_min')}, dpi {d.get('dpi')}, "
          f"limite_mb {d.get('limite_mb')}, salida {d.get('salida')}, sin_descargas {d.get('sin_descargas')}, max_candidatos {d.get('max_candidatos')}")
    if not (d.get("percentil") == 99 and d.get("tam_min") == 20 and d.get("dpi") == 150 and d.get("limite_mb") == 120
            and d.get("sin_descargas") is True and d.get("delante") == [13, 14, 15] and d.get("max_candidatos") == 0
            and os.path.normcase(d.get("salida", "")) == os.path.normcase(SALIDA)):
        malos.append("valores válidos en el JSON")
    if WIN and "APPDATA" in os.environ and not str(arch).lower().startswith(os.environ["APPDATA"].lower()):
        malos.append(f"el JSON no está en APPDATA ({arch})")
    if malos:
        raise SystemExit("FALLO: no se han conservado: " + ", ".join(malos))
    print("PRUEBA DE AJUSTES OK: todo se conserva entre sesiones (cerrando con la X)")
    if WIN:
        return
    # ---- 3ª sesión: «Restablecer valores» + «Salir» -> la 4ª abre con los valores por defecto
    p, L = lanzar({})
    esperar(L, r"PRUEBA panel abierto")
    pos = json_de(ultima(L, r"PRUEBA panel abierto"))
    xdo("mousemove", *pos["restablecer"], "click", 1); time.sleep(0.5)
    xdo("mousemove", *pos["salir"], "click", 1)
    p.wait(30)
    p, L = lanzar({})
    vals = json_de(esperar(L, r"PRUEBA valores"))
    time.sleep(0.5); cerrar_con_x(); p.wait(30)
    t = vals["textos"]
    ok = (t["percentil"] == "98.5" and t["tam_min"] == "30" and t["dpi"] == "110" and t["limite_mb"] == "180"
          and t["max_candidatos"] == "0" and t["sin_descargas"] is False and t["delante"] == "14,15,16")
    print(f"   tras Restablecer + Salir: percentil {t['percentil']}, tam_min {t['tam_min']}, dpi {t['dpi']}, "
          f"limite_mb {t['limite_mb']}, sin_descargas {t['sin_descargas']}  {'OK' if ok else 'MAL'}")
    if not ok:
        raise SystemExit("FALLO: «Restablecer valores» + «Salir» no dejó guardados los valores por defecto")
    print("PRUEBA DE RESTABLECER OK")


def _num(x):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None


if __name__ == "__main__":
    main()
