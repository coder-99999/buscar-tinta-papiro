# -*- coding: utf-8 -*-
"""
MCSerDeLuz - Buscar tinta en el papiro (PHerc 1447 y otros segmentos del Vesuvius Challenge)
===========================================================================================

Busca INDICIOS de tinta en los segmentos ya descargados (zip o carpeta), SIN modelo de IA,
con cuatro medidas clásicas sobre las capas de la superficie del papiro:

  1. Densidad anómala: la capa de superficie comparada con su fondo suavizado (puntuación z).
  2. Textura / fibras rotas: coherencia de la orientación de las fibras y desviación local.
  3. Diferencia entre capas: capas delanteras (14-16) frente a las de detrás (17-20).
  4. "Crujido": energía de alta frecuencia (opcional).

Las combina en una puntuación, busca manchas compactas del tamaño de un trazo (30-80 px a
8,64 µm, unos 0,3-0,7 mm), descarta bordes y agujeros y guarda un informe de texto en español,
un mapa PNG y una lámina con los mejores candidatos.

AVISO: la tinta de carbono de Herculano casi no cambia la densidad del papiro. Lo que encuentra
este programa son PISTAS DÉBILES para mirar con más calma, NO pruebas de escritura.

MODO BARRIDO (botón «Barrido PHerc 1447» o --barrido): recorre los segmentos oficiales pequeños de
PHerc 1447 (180 MB o menos; usa los zips que ya tengas y, si no, descarga del bucket público del
Vesuvius Challenge unos 100 MB por segmento), con los mapas del barrido (densidad, pérdida de fibra,
textura, entre capas, crackle), umbral z>4, manchas de 25-160 px a más de 45 px de bordes y agujeros,
controles contra falsos positivos y una clasificación «qué es». Tabla TXT + CSV y PNG por segmento.

Uso:
  - Doble clic en buscar_tinta_papiro.bat (o en este archivo .py): se abre una ventana para elegir.
  - Terminal:  py buscar_tinta_papiro.py                      (ventana para elegir segmento)
               py buscar_tinta_papiro.py RUTA.zip               (analiza ese zip o carpeta)
               py buscar_tinta_papiro.py RUTA.zip --sin-ventana (solo informe y PNG, sin ventanas)
               py buscar_tinta_papiro.py --sin-ventana          (analiza todos los que encuentre)
               py buscar_tinta_papiro.py --barrido --sin-ventana  (barrido de PHerc 1447)
               py buscar_tinta_papiro.py --ayuda                (todas las opciones)

Librerías: numpy y matplotlib (obligatorias); numcodecs (viene con zarr) para zarr comprimidos;
tifffile para segmentos en TIFF; scipy opcional (más rápido). Instalar todo:
  py -m pip install numpy zarr tifffile matplotlib scipy

CRÉDITOS Y LICENCIAS
  * Mapas y umbrales del barrido: an.py, barrido previo de MCSerDeLuz (sin IA).
  * Controles contra falsos positivos (capas vecinas, orden de profundidad invertido, bordes y
    agujeros de la malla) y orquestación del barrido (conexión persistente con reintentos, escritura
    atómica, reanudar lo ya hecho): ideas y funciones adaptadas de «first-letters-survey» de
    Matteo Bulloni (https://github.com/Bullo27/first-letters-survey). NO se usa ninguno de sus
    modelos de IA. Su licencia:

      MIT License
      Copyright (c) 2026 Matteo Bulloni
      Permission is hereby granted, free of charge, to any person obtaining a copy of this software
      and associated documentation files (the "Software"), to deal in the Software without
      restriction, including without limitation the rights to use, copy, modify, merge, publish,
      distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
      Software is furnished to do so, subject to the following conditions:
      The above copyright notice and this permission notice shall be included in all copies or
      substantial portions of the Software.
      THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
      BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
      NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
      DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
      OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

  * «Omit» de Timo Meireman: su código no es accesible públicamente (carpeta de OneDrive con
    acceso restringido) y no se ha encontrado licencia, así que NO se ha copiado nada. Solo se
    ha tenido en cuenta la idea general descrita en público (comparar la superficie con capas
    vecinas sin IA), reimplementada desde cero.
  * Datos: Vesuvius Challenge, datos abiertos (https://scrollprize.org/data).
"""
VERSION = "2.0 (2026-10-31)"

import sys, os

# ---------------------------------------------------------------- consola en UTF-8 (Windows)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.version_info < (3, 8):
    print("Este programa necesita Python 3.8 o más moderno. Tienes", sys.version.split()[0])
    print("Instala Python 3.12 con:  winget install Python.Python.3.12")
    sys.exit(1)

SIN_VENTANA = any(a.lower() in ("--sin-ventana", "--sinventana", "--headless") for a in sys.argv[1:])


def _aviso_grave(titulo, texto):
    """Muestra un error en la consola y, si se puede, también en una ventanita."""
    print("\n" + "=" * 70 + "\n" + titulo + "\n" + "-" * 70 + "\n" + texto + "\n" + "=" * 70)
    if not SIN_VENTANA:
        try:
            import tkinter as _tk
            from tkinter import messagebox as _mb
            r = _tk.Tk(); r.withdraw()
            _mb.showerror(titulo, texto)
            r.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------- librerías
_faltan = []
try:
    import numpy as np
except ImportError:
    _faltan.append("numpy")
try:
    import matplotlib
except ImportError:
    _faltan.append("matplotlib")
if _faltan:
    _aviso_grave("Faltan librerías de Python",
                 "Falta: " + ", ".join(_faltan) + "\n\n"
                 + ("Instálalas abriendo PowerShell y escribiendo:\n"
                    "    py -m pip install numpy zarr tifffile matplotlib scipy\n\n"
                    "(si 'py' no existe, prueba con 'python -m pip install ...')" if os.name == "nt" else
                    "Instálalas en un entorno virtual (Linux):\n"
                    "    python3 -m venv ~/.venv-buscar-tinta\n"
                    "    ~/.venv-buscar-tinta/bin/pip install numpy zarr tifffile matplotlib scipy\n"
                    "y abre el programa con ./buscar_tinta_papiro.sh (usa ese entorno solo).\n"
                    "(en Debian/Ubuntu quizá antes: sudo apt install python3-venv python3-tk)"))
    sys.exit(1)

if SIN_VENTANA:
    matplotlib.use("Agg")
else:
    try:
        import tkinter  # noqa: F401
        matplotlib.use("TkAgg")
    except Exception:
        matplotlib.use("Agg")
        SIN_VENTANA = True
        print("Aviso: no hay tkinter en este Python, así que no puedo abrir ventanas. "
              "Sigo en modo texto (informe y PNG).")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

try:
    import numcodecs
except ImportError:
    numcodecs = None
try:
    import tifffile
except ImportError:
    tifffile = None
try:
    from scipy import ndimage as ndi
except ImportError:
    ndi = None

import io, re, json, math, time, zipfile, argparse, datetime, csv
from pathlib import Path

# ============================== AJUSTES ==============================================
CAPAS_DELANTE = [14, 15, 16]        # capas de la cara donde buscamos tinta (31 capas, 15 = centro)
CAPAS_DETRAS = [17, 18, 19, 20]     # capas de comparación
TAM_PIXEL_UM = 8.64                 # tamaño del píxel del segmento (micras)
TAM_TRAZO_MIN, TAM_TRAZO_MAX = 30, 80   # tamaño de un trazo (píxeles del segmento)
RADIO_FONDO = 75                    # radio del fondo suavizado (px): ~1,3 mm
MARGEN_BORDE = 30                   # se descartan manchas a menos de esto del borde / agujeros
PESOS = {"densidad": 0.35, "textura": 0.25, "capas": 0.25, "crujido": 0.15}
PERCENTIL_UMBRAL = 98.5             # qué parte alta de la puntuación se considera mancha
MAX_PIXELES = 30_000_000            # por encima, se reduce la resolución para no agotar la memoria
MAX_CANDIDATOS = 15
NOMBRE_RESULTADOS = "MCSerDeLuz-resultados-tinta"
# ====================================================================================

CARPETA_PROGRAMA = Path(os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__)).parent


# ------------------------------------------------------------------ barra de progreso
def _hms(seg):
    seg = int(max(0, seg))
    return f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}" if seg >= 3600 else f"{seg // 60}:{seg % 60:02d}"


class Progreso:
    """Barra de progreso con tiempo restante: en la consola (texto) y, si hay ventana, con ttk.Progressbar.
    El trabajo total se reparte en tramos (uno por segmento) y cada tramo en fases."""

    def __init__(self):
        self.t0 = time.time()
        self.tramo_ = (0.0, 1.0)
        self.fase_ = (0.0, 1.0)
        self.g = 0.0
        self.ultimo = (-1.0, 0.0)
        self.raiz = None
        self.cancelado = False
        self.tty = bool(getattr(sys.stdout, "isatty", lambda: False)())

    def iniciar(self, titulo="", ventana=False):
        self.t0 = time.time(); self.g = 0.0; self.ultimo = (-1.0, 0.0)
        self.tramo_ = (0.0, 1.0); self.fase_ = (0.0, 1.0)
        if ventana:
            try:
                import tkinter as tk
                from tkinter import ttk
                r = tk.Tk()
                r.title("MCSerDeLuz - " + (titulo or "trabajando..."))
                r.geometry("620x150")
                self.lbl = tk.Label(r, text=titulo, font=("Segoe UI", 11, "bold")); self.lbl.pack(pady=(12, 4))
                self.barra = ttk.Progressbar(r, orient="horizontal", length=560, mode="determinate", maximum=1000)
                self.barra.pack(pady=4)
                self.eta = tk.Label(r, text="", font=("Segoe UI", 10)); self.eta.pack()
                tk.Button(r, text="Cancelar", command=self._cancelar).pack(pady=4)
                r.protocol("WM_DELETE_WINDOW", self._cancelar)
                self.raiz = r
                r.update()
            except Exception as e:
                print("(no puedo abrir la ventana de progreso: " + str(e) + ")")
                self.raiz = None

    def _cancelar(self):
        self.cancelado = True

    def cerrar(self):
        if self.raiz is not None:
            try:
                self.raiz.destroy()
            except Exception:
                pass
            self.raiz = None

    def tramo(self, a, b):
        self.tramo_ = (a, b); self.fase_ = (0.0, 1.0)

    def fase(self, a, b, texto=None):
        self.fase_ = (a, b)
        self.poner(0.0, texto)

    def texto_eta(self):
        t = time.time() - self.t0
        if self.g >= 0.999:
            return f"terminado en {_hms(t)}"
        if self.g < 0.02 or t < 2:
            return f"transcurrido {_hms(t)}, calculando el tiempo restante..."
        return f"transcurrido {_hms(t)}, quedan unos {_hms(t / self.g * (1 - self.g))}"

    def poner(self, x, texto=None):
        if self.cancelado:
            self.cancelado = False
            raise KeyboardInterrupt
        a, b = self.fase_
        A, B = self.tramo_
        g = A + (B - A) * (a + (b - a) * min(max(x, 0.0), 1.0))
        self.g = max(self.g, min(g, 1.0))
        ahora = time.time()
        gu, tu = self.ultimo
        if self.g - gu >= 0.05 or ahora - tu >= 15 or self.g >= 0.999 and gu < 0.999:
            self.ultimo = (self.g, ahora)
            n = int(round(30 * self.g))
            print(f"  [{'#' * n}{'-' * (30 - n)}] {self.g * 100:5.1f} %  {self.texto_eta()}", flush=True)
        if self.raiz is not None:
            try:
                self.barra["value"] = int(1000 * self.g)
                self.eta["text"] = f"{self.g * 100:.0f} %  -  {self.texto_eta()}"
                if texto:
                    self.lbl["text"] = texto[:80]
                self.raiz.update()
            except Exception:
                self.raiz = None


PROG = Progreso()
_FASES = {1: (0.0, 0.02), 2: (0.02, 0.25), 3: (0.25, 0.3), 4: (0.3, 0.75), 5: (0.75, 0.88), 6: (0.88, 1.0)}


def paso(n, total, texto):
    print(f"[{n}/{total}] {texto}", flush=True)
    if total == 6:
        PROG.fase(*_FASES[n], texto=texto)


def abrir_carpeta(carpeta):
    """Abre la carpeta en el explorador (Windows, Linux o Mac)."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(carpeta))
        else:
            import subprocess, shutil
            prog = shutil.which("xdg-open") or shutil.which("open")
            if prog:
                subprocess.Popen([prog, str(carpeta)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def mb(nbytes):
    return f"{nbytes / 1e6:,.1f} MB".replace(",", " ")


# ====================================================================================
#  FILTROS (solo numpy; usa scipy si está, que es más rápido)
# ====================================================================================
def _suma_caja_1d(a, r, eje):
    a = np.moveaxis(a, eje, 0)
    n = a.shape[0]
    c = np.zeros((n + 1,) + a.shape[1:], dtype=np.float64)
    np.cumsum(a, axis=0, dtype=np.float64, out=c[1:])
    i = np.arange(n)
    lo = np.clip(i - r, 0, n)
    hi = np.clip(i + r + 1, 0, n)
    s = (c[hi] - c[lo]).astype(np.float32)
    return np.moveaxis(s, 0, eje)


def suma_caja(a, r):
    """Suma en una ventana cuadrada de lado 2r+1 (truncada en los bordes)."""
    r = int(max(0, r))
    if r == 0:
        return a.astype(np.float32)
    if ndi is not None:
        k = 2 * r + 1
        return (ndi.uniform_filter(a.astype(np.float32), size=k, mode="constant") * (k * k)).astype(np.float32)
    return _suma_caja_1d(_suma_caja_1d(a.astype(np.float32), r, 0), r, 1)


def media_mascara(x, m, r):
    """Media local de x usando solo los píxeles de la máscara m."""
    num = suma_caja(x * m, r)
    den = suma_caja(m, r)
    return num / np.maximum(den, 1e-6)


def suavizar(x, m, r):
    """Suavizado aproximadamente gaussiano (dos cajas) respetando la máscara."""
    if r <= 0:
        return x
    y = media_mascara(x, m, r)
    return media_mascara(y, m, r) * m


def puntuacion_z(x, m, r_fondo):
    """(x - fondo local) / desviación local, dentro de la máscara."""
    fondo = media_mascara(x, m, r_fondo)
    res = (x - fondo) * m
    var = media_mascara(res * res, m, r_fondo)
    z = res / np.sqrt(np.maximum(var, 1e-6))
    return np.clip(z, -8, 8).astype(np.float32) * m


def etiquetar(b):
    """Componentes conexas (8 vecinos). Devuelve (etiquetas, n)."""
    if ndi is not None:
        lab, n = ndi.label(b, structure=np.ones((3, 3), bool))
        return lab, n
    H, W = b.shape
    lab = np.zeros((H, W), np.int32)
    ys, xs = np.nonzero(b)
    n = 0
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        pila = [(y0, x0)]
        while pila:
            y, x = pila.pop()
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= H:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < W and b[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        pila.append((yy, xx))
    return lab, n


# ====================================================================================
#  LECTURA DE SEGMENTOS (zip o carpeta; zarr v2, zarr v3 o carpeta layers/ de TIFF)
# ====================================================================================
class Origen:
    """Acceso de solo lectura a archivos dentro de un zip o de una carpeta."""

    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.es_zip = self.ruta.is_file() and zipfile.is_zipfile(self.ruta)
        if self.es_zip:
            self.zf = zipfile.ZipFile(self.ruta)
            self.nombres = [n for n in self.zf.namelist() if not n.endswith("/")]
        else:
            self.zf = None
            base = self.ruta
            self.nombres = []
            for raiz, dirs, archivos in os.walk(base):
                for a in archivos:
                    self.nombres.append(Path(raiz, a).relative_to(base).as_posix())

    def leer(self, nombre):
        if self.zf is not None:
            return self.zf.read(nombre)
        with open(self.ruta / nombre, "rb") as f:
            return f.read()

    def cerrar(self):
        if self.zf is not None:
            self.zf.close()


def buscar_volumen(origen, nivel="0"):
    """Encuentra dentro del zip/carpeta el volumen de superficie a resolución completa."""
    nombres = origen.nombres
    zarrays = [n for n in nombres if n.endswith("/.zarray") or n == ".zarray"]
    # Preferimos surface-volumes/<algo>.zarr/0/.zarray (nivel 0 = resolución completa)
    cand = []
    for n in zarrays:
        d = n[: -len(".zarray")].rstrip("/")
        partes = d.split("/") if d else []
        nivel0 = bool(partes) and partes[-1] == nivel
        sv = "surface-volume" in n
        cand.append((0 if nivel0 else 1, 0 if sv else 1, len(n), d))
    if cand:
        cand.sort()
        return ("zarr2", cand[0][3])
    zj = [n for n in nombres if n.endswith("zarr.json")]
    if zj:
        return ("zarr3", zj)
    tifs = [n for n in nombres if re.search(r"(^|/)layers/\d+\.tiff?$", n, re.I)]
    if tifs:
        return ("tif", sorted(tifs, key=lambda s: int(re.search(r"(\d+)\.tiff?$", s, re.I).group(1))))
    return (None, None)


def id_segmento(ruta, interno=""):
    for texto in (str(ruta), interno):
        m = re.findall(r"(\d{14})", texto)
        if m:
            return m[0]
    return Path(ruta).stem


class Volumen:
    """Lee capas sueltas del volumen sin cargarlo entero."""

    def __init__(self, ruta, nivel="0"):
        self.ruta = Path(ruta)
        self.origen = Origen(ruta)
        self.tipo, self.ref = buscar_volumen(self.origen, nivel)
        if self.tipo is None:
            self.origen.cerrar()
            raise ValueError("No encuentro capas de papiro (zarr ni carpeta layers/) en " + str(ruta))
        self.interno = self.ref if isinstance(self.ref, str) else (self.ref[0] if self.ref else "")
        self.segmento = id_segmento(ruta, self.interno)
        self.trozos = None
        if self.tipo == "zarr2":
            pref = (self.ref + "/") if self.ref else ""
            self.meta = json.loads(self.origen.leer(pref + ".zarray"))
            self.forma = tuple(int(v) for v in self.meta["shape"])
            self.trozo = tuple(int(v) for v in self.meta["chunks"])
            self.dtype = np.dtype(self.meta["dtype"])
            self.sep = self.meta.get("dimension_separator", ".") or "."
            self.orden = self.meta.get("order", "C")
            comp = self.meta.get("compressor")
            self.codec = None
            if comp:
                if numcodecs is None:
                    raise RuntimeError("El segmento está comprimido (" + str(comp.get("id")) + ") y falta la librería "
                                       "'numcodecs'.\nInstálala con:  py -m pip install zarr   (trae numcodecs)")
                self.codec = numcodecs.get_codec(comp)
            self.filtros = [numcodecs.get_codec(f) for f in (self.meta.get("filters") or [])] if numcodecs else []
            if self.meta.get("filters") and numcodecs is None:
                raise RuntimeError("Falta 'numcodecs'. Instálala con:  py -m pip install zarr")
            self.llaves = []
            for n in self.origen.nombres:
                if not n.startswith(pref):
                    continue
                resto = n[len(pref):]
                if resto.startswith("."):
                    continue
                trozos = resto.split(self.sep)
                if len(trozos) == 3 and all(t.isdigit() for t in trozos):
                    self.llaves.append((tuple(int(t) for t in trozos), n))
            N_, H_, W_ = self.forma
            cz_, cy_, cx_ = self.trozo
            self.trozos = (len(self.llaves), math.ceil(N_ / cz_) * math.ceil(H_ / cy_) * math.ceil(W_ / cx_))
        elif self.tipo == "zarr3":
            self._abrir_zarr3()
        else:  # tif
            if tifffile is None:
                raise RuntimeError("Este segmento viene en TIFF y falta 'tifffile'.\nInstálala con:  py -m pip install tifffile")
            primera = tifffile.imread(io.BytesIO(self.origen.leer(self.ref[0])))
            self.forma = (len(self.ref),) + tuple(primera.shape[:2])
            self.dtype = primera.dtype

    def _abrir_zarr3(self):
        try:
            import zarr
        except ImportError:
            raise RuntimeError("Este segmento usa zarr v3 y falta la librería 'zarr'.\nInstálala con:  py -m pip install zarr")
        if not str(getattr(zarr, "__version__", "2")).startswith("3"):
            raise RuntimeError("Este segmento usa zarr v3 y tienes zarr " + str(zarr.__version__) +
                               ".\nActualízala con:  py -m pip install --upgrade zarr")
        arrays = []
        for n in self.ref:
            meta = json.loads(self.origen.leer(n))
            if meta.get("node_type") == "array" and len(meta.get("shape", [])) == 3:
                arrays.append((n, meta))
        if not arrays:
            raise ValueError("No encuentro un array 3D en el zarr v3")
        arrays.sort(key=lambda t: (-int(np.prod(t[1]["shape"])), len(t[0])))
        nombre, meta = arrays[0]
        ruta_arr = nombre[: -len("zarr.json")].rstrip("/")
        if self.origen.es_zip:
            store = zarr.storage.ZipStore(str(self.ruta), mode="r")
        else:
            store = zarr.storage.LocalStore(str(self.ruta), read_only=True)
        self.z3 = zarr.open_array(store=store, path=ruta_arr, mode="r")
        self.forma = tuple(int(v) for v in self.z3.shape)
        self.dtype = self.z3.dtype
        self.interno = ruta_arr

    # ---------------------------------------------------------------
    def leer_pila(self, capas, f=1):
        """Lee solo las capas pedidas (reducidas f veces) y devuelve (pila uint8 [L, h, w], {capa: índice})."""
        N, H, W = self.forma
        h, w = H // f, W // f
        capas = sorted({int(c) for c in capas if 0 <= int(c) < N})
        idx = {c: i for i, c in enumerate(capas)}
        pila = np.zeros((len(capas), h, w), np.uint8)

        def reducir(bloque):  # (L, hh, ww), hh y ww múltiplos de f
            if f == 1:
                return bloque
            L, hh, ww = bloque.shape
            r = bloque.reshape(L, hh // f, f, ww // f, f).astype(np.float32).mean(axis=(2, 4))
            return np.clip(np.rint(r), 0, 255).astype(np.uint8)

        def a_uint8(x):
            if x.dtype == np.uint8:
                return x
            if x.dtype == np.uint16:
                return (x >> 8).astype(np.uint8)
            return np.clip(x, 0, 255).astype(np.uint8)

        if self.tipo == "zarr2":
            cz, cy, cx = self.trozo
            if cy % f or cx % f:
                raise RuntimeError("Tamaño de trozo no divisible por la reducción; usa --reduccion 1")
            por_xy = {}
            for p, n in self.llaves:
                if any(p[0] * cz <= c < (p[0] + 1) * cz for c in capas):
                    por_xy.setdefault((p[1], p[2]), []).append((p[0], n))
            total = len(por_xy)
            ultimo = -1
            for k, ((iy, ix), lista) in enumerate(sorted(por_xy.items())):
                y0, x0 = iy * cy, ix * cx
                hh = min(cy, H - y0) // f * f
                ww = min(cx, W - x0) // f * f
                if hh <= 0 or ww <= 0:
                    continue
                bloque = np.zeros((len(capas), hh, ww), np.uint8)
                for iz, n in lista:
                    raw = self.origen.leer(n)
                    if self.codec is not None:
                        raw = self.codec.decode(raw)
                    for flt in reversed(self.filtros):
                        raw = flt.decode(raw)
                    arr = np.frombuffer(raw, dtype=self.dtype)
                    if arr.size != cz * cy * cx:
                        continue
                    arr = arr.reshape((cz, cy, cx), order=self.orden)
                    for c in capas:
                        if iz * cz <= c < (iz + 1) * cz:
                            bloque[idx[c]] = a_uint8(arr[c - iz * cz, :hh, :ww])
                red = reducir(bloque)
                pila[:, y0 // f:y0 // f + red.shape[1], x0 // f:x0 // f + red.shape[2]] = red
                pct = int(100 * (k + 1) / max(total, 1))
                if (k & 7) == 0 or k + 1 == total:
                    PROG.poner((k + 1) / max(total, 1), "leyendo trozos del zarr...")
        else:
            for i, c in enumerate(capas):
                if self.tipo == "zarr3":
                    capa = np.asarray(self.z3[c])
                else:
                    capa = tifffile.imread(io.BytesIO(self.origen.leer(self.ref[c])))
                    if capa.ndim == 3:
                        capa = capa[..., 0]
                capa = a_uint8(capa[: h * f, : w * f])
                red = reducir(capa[None])[0]
                pila[i, : red.shape[0], : red.shape[1]] = red
                PROG.poner((i + 1) / len(capas), f"capa {c} leída")
        return pila, idx

    def cerrar(self):
        self.origen.cerrar()


# ====================================================================================
#  BÚSQUEDA AUTOMÁTICA DE SEGMENTOS
# ====================================================================================
def carpetas_busqueda():
    casa = Path.home()
    c = [CARPETA_PROGRAMA, casa / "Desktop", casa / "Escritorio", casa / "OneDrive" / "Desktop",
         casa / "OneDrive" / "Escritorio", casa / "Downloads", casa / "Descargas",
         casa / "Documents" / "Papiro", casa / "Documentos" / "Papiro", casa / "OneDrive" / "Documents" / "Papiro"]
    xdg = os.environ.get("XDG_DESKTOP_DIR")
    if not xdg and os.name != "nt":
        try:
            cfg = (casa / ".config" / "user-dirs.dirs").read_text("utf-8", "replace")
            m_ = re.search(r'XDG_DESKTOP_DIR="([^"]+)"', cfg)
            xdg = m_.group(1).replace("$HOME", str(casa)) if m_ else None
        except Exception:
            xdg = None
    if xdg:
        c.insert(1, Path(xdg))
    vistas, res = set(), []
    for d in c:
        try:
            k = d.resolve()
        except Exception:
            continue
        if d.is_dir() and k not in vistas:
            vistas.add(k)
            res.append(d)
    return res


def parece_segmento_zip(p):
    try:
        with zipfile.ZipFile(p) as zf:
            for n in zf.namelist():
                if n.endswith(".zarray") or n.endswith("zarr.json") or re.search(r"(^|/)layers/\d+\.tiff?$", n, re.I):
                    return True
    except Exception:
        return False
    return False


def buscar_segmentos(carpetas=None, profundidad=2):
    encontrados = []
    vistos = set()
    for base in carpetas or carpetas_busqueda():
        pila = [(base, 0)]
        while pila:
            d, nivel = pila.pop()
            try:
                entradas = list(os.scandir(d))
            except Exception:
                continue
            for e in entradas:
                try:
                    if e.is_file() and e.name.lower().endswith(".zip"):
                        if parece_segmento_zip(e.path):
                            k = os.path.realpath(e.path)
                            if k not in vistos:
                                vistos.add(k)
                                encontrados.append(Path(e.path))
                    elif e.is_dir() and not e.name.startswith((".", "$")) and e.name != NOMBRE_RESULTADOS:
                        sv = Path(e.path) / "surface-volumes"
                        lay = Path(e.path) / "layers"
                        if sv.is_dir() or lay.is_dir():
                            k = os.path.realpath(e.path)
                            if k not in vistos:
                                vistos.add(k)
                                encontrados.append(Path(e.path))
                        elif nivel < profundidad:
                            pila.append((Path(e.path), nivel + 1))
                except Exception:
                    continue
    # el mismo segmento en zip y en carpeta: basta con uno (preferimos el zip)
    encontrados.sort(key=lambda p: (0 if str(p).lower().endswith(".zip") else 1))
    unicos, ids = [], set()
    for p in encontrados:
        k = id_segmento(p)
        if k in ids:
            continue
        ids.add(k)
        unicos.append(p)
    return unicos


def tam_en_disco(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size
    total = 0
    for raiz, _, archivos in os.walk(p):
        for a in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
    return total


# ====================================================================================
#  FILTROS EXTRA (gaussiano aproximado, Sobel, distancias) — sin OpenCV
# ====================================================================================
def G(x, s):
    """Desenfoque gaussiano de sigma s. Con sigma grande usa tres cajas (rápido y casi igual)."""
    x = np.asarray(x, np.float32)
    if s <= 0:
        return x
    if ndi is not None and s <= 12:
        return ndi.gaussian_filter(x, s, mode="reflect", truncate=3.0).astype(np.float32)
    r = max(1, int(round((math.sqrt(4 * s * s + 1) - 1) / 2)))
    uno = np.ones(x.shape, np.float32)
    cnt = suma_caja(uno, r)
    for _ in range(3):
        x = suma_caja(x, r) / cnt
    return x.astype(np.float32)


def bgsub(x, m, s):
    mf = m.astype(np.float32)
    b = G(x * mf, s) / np.maximum(G(mf, s), 1e-3)
    return (x - b) * mf


def zG(x, m, s=150):
    """Puntuación z frente al fondo local (ventana gaussiana s) solo dentro de m."""
    mf = m.astype(np.float32)
    den = np.maximum(G(mf, s), 1e-3)
    mu = G(x * mf, s) / den
    var = G(((x - mu) ** 2) * mf, s) / den
    return np.where(m, (x - mu) / np.sqrt(var + 1e-6), 0).astype(np.float32)


def sobel(x):
    p = np.pad(x, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return gx.astype(np.float32), gy.astype(np.float32)


def erosionar(m, r):
    """Píxeles de m a más de r px de cualquier hueco o borde."""
    if r <= 0:
        return m.copy()
    if ndi is not None:
        return ndi.distance_transform_edt(m) > r
    return (suma_caja(m.astype(np.float32), r) >= (2 * r + 1) ** 2 - 0.5) & m


def dilatar(m, r):
    if r <= 0:
        return m.copy()
    return suma_caja(m.astype(np.float32), r) > 0.5


def limpiar_mascara(m0, f):
    """Apertura y quitar islas pequeñas (como el barrido de la caja)."""
    if ndi is not None:
        m0 = ndi.binary_opening(m0, iterations=2)
        lab, n = ndi.label(m0)
        if n:
            sz = ndi.sum(m0, lab, range(1, n + 1))
            m0 = np.isin(lab, 1 + np.where(sz > 20000 / (f * f))[0])
        return m0
    m0 = dilatar(erosionar(m0, 2), 2) & m0
    k = 8  # islas a 1/8 de resolución (rápido sin scipy)
    h, w = m0.shape[0] // k, m0.shape[1] // k
    if h and w:
        peq = m0[: h * k, : w * k].reshape(h, k, w, k).mean(axis=(1, 3)) > 0.5
        lab, n = etiquetar(peq)
        if n:
            sz = np.bincount(lab.ravel())
            buenas = np.where(sz * k * k * f * f > 20000)[0]
            buenas = buenas[buenas > 0]
            ok = np.isin(lab, buenas)
            grande = np.kron(ok, np.ones((k, k), bool))
            mm = np.zeros_like(m0); mm[: h * k, : w * k] = grande
            m0 = m0 & mm
    return m0


def objetos(lab, n):
    if ndi is not None:
        return ndi.find_objects(lab)
    objs = [None] * n
    ys, xs = np.nonzero(lab)
    if ys.size:
        ls = lab[ys, xs]
        o = np.argsort(ls, kind="stable")
        ys, xs, ls = ys[o], xs[o], ls[o]
        cortes = np.flatnonzero(np.diff(ls)) + 1
        for a, b, l in zip(np.split(ys, cortes), np.split(xs, cortes), np.split(ls, cortes)):
            objs[l[0] - 1] = (slice(a.min(), a.max() + 1), slice(b.min(), b.max() + 1))
    return objs


# ====================================================================================
#  CONTROLES CONTRA FALSOS POSITIVOS Y "¿QUÉ ES?"
#  Adaptados de first-letters-survey de Matteo Bulloni (licencia MIT, ver CRÉDITOS):
#  comparación con las capas vecinas (mancha frente a su anillo de alrededor, capa a capa),
#  orden de profundidad invertido y rechazo de bordes y agujeros de la malla.
# ====================================================================================
TIPOS = {
    "grano": ("grano brillante / inclusión", "yellow"),
    "fibra": ("fibra o separación de capas", "lime"),
    "motas": ("motas sueltas", "magenta"),
    "trazo": ("grupo tipo trazo", "red"),
    "aislado": ("aislado, sin explicar (débil)", "cyan"),
}
COLOR_ES = {"yellow": "amarillo", "lime": "verde", "magenta": "magenta", "red": "rojo", "cyan": "cian"}
LEYENDA = "  ".join(f"{COLOR_ES[v[1]]} = {v[0]}" for v in TIPOS.values())


def lados_vecinos(centro):
    return [centro - 5, centro - 4, centro - 3], [centro + 4, centro + 5, centro + 6]


def controles(c, sl, reg, pila, idx, f, S, m0, dist, p995, mapa_fwd, mapa_rev, lado_a, lado_b, delante):
    """Mide la mancha (sl, reg) en cada capa frente a su entorno y calcula los controles."""
    y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
    hh, ww = y1 - y0, x1 - x0
    pad = max(hh, ww, int(20 / f))
    Y0, Y1 = max(0, y0 - pad), min(S.shape[0], y1 + pad)
    X0, X1 = max(0, x0 - pad), min(S.shape[1], x1 + pad)
    regW = np.zeros((Y1 - Y0, X1 - X0), bool)
    regW[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = reg
    anillo = (~dilatar(regW, max(1, int(4 / f)))) & m0[Y0:Y1, X0:X1]
    perfil = {}
    for capa, i in idx.items():
        v = pila[i, Y0:Y1, X0:X1].astype(np.float32)
        if anillo.sum() < 20 or regW.sum() < 3:
            perfil[capa] = 0.0
            continue
        a = v[anillo]
        perfil[capa] = float((v[regW].mean() - a.mean()) / (a.std() + 1e-3))
    med = lambda L: float(np.mean([perfil[k] for k in L if k in perfil])) if any(k in perfil for k in L) else 0.0
    c["perfil"] = {int(k): round(v, 2) for k, v in sorted(perfil.items())}
    c["sup"] = med(delante)
    c["vec_a"] = med(lado_a)
    c["vec_b"] = med(lado_b)
    c["fwd"] = float(mapa_fwd[sl][reg].mean())
    c["rev"] = float(mapa_rev[sl][reg].mean())
    c["saturado"] = float((S[sl][reg] >= p995).mean())
    yy, xx = np.nonzero(reg)
    if yy.size > 2:
        cov = np.cov(np.vstack([yy, xx]).astype(np.float64))
        ev = np.sort(np.linalg.eigvalsh(cov))
        c["elong"] = float(math.sqrt(max(ev[1], 1e-6) / max(ev[0], 1e-6)))
    else:
        c["elong"] = 1.0
    if dist is not None:
        c["dist_borde"] = int(dist[sl][reg].min() * f)
    else:
        d = 0
        for r in (5, 10, 20, 45, 90, 180):
            if erosionar_ventana(m0, sl, int(r / f)):
                d = r
            else:
                break
        c["dist_borde"] = d


def erosionar_ventana(m0, sl, r):
    y0, y1, x0, x1 = sl[0].start - r, sl[0].stop + r, sl[1].start - r, sl[1].stop + r
    if y0 < 0 or x0 < 0 or y1 > m0.shape[0] or x1 > m0.shape[1]:
        return False
    return bool(m0[y0:y1, x0:x1].all())


def agrupar(cands, radio=250):
    P = np.array([[c["fila"], c["col"]] for c in cands], float) if cands else np.zeros((0, 2))
    for i, c in enumerate(cands):
        if len(P) > 1:
            d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
            c["vecinos"] = int((d < radio).sum() - 1)
        else:
            c["vecinos"] = 0


def clasificar(c):
    """Regla sencilla y transparente (no es IA)."""
    mapas = c.get("mapas", [])
    if (c["vec_a"] > 1.0 and c["vec_b"] > 1.0) or c["saturado"] > 0.3:
        t = "grano"      # sigue en las capas de ambos lados o está saturado: objeto 3D denso, no tinta de superficie
    elif (mapas and set(mapas) <= {"crackle", "crujido"}) or c["area"] < 300 or \
            (c.get("crujido", 0) > 2.5 and c.get("crujido", 0) > 2 * max(c.get("densidad", 0), c.get("capas", 0))):
        t = "motas"     # puntitos de alta frecuencia o manchas diminutas
    elif c["elong"] >= 2.5 or (mapas and set(mapas) <= {"perdida_fibra", "entre_capas", "capas"}) \
            or (c["fwd"] > 1 and c["rev"] >= 0.8 * c["fwd"]):
        t = "fibra"     # alargado, o igual en el orden inverso: estructura del papiro, no superficie
    elif c["vecinos"] >= 2 and c["sup"] > max(c["vec_a"], c["vec_b"]) + 0.5 and c["fwd"] > c["rev"] + 0.3:
        t = "trazo"
    else:
        t = "aislado"
    c["tipo"] = t
    c["que_es"] = TIPOS[t][0]


# ====================================================================================
#  ANÁLISIS DE UN SEGMENTO (modo normal)
# ====================================================================================
def ajustar_capas(lista, N):
    """Las capas están pensadas para 31 (centro 15); si hay otro número, se desplazan."""
    despl = N // 2 - 15
    res = [c + despl for c in lista]
    validas = [c for c in res if 0 <= c < N]
    return validas, despl


def elegir_reduccion(H, W, pedida):
    f = pedida
    if f <= 0:
        f = 1
        while (H // f) * (W // f) > MAX_PIXELES:
            f *= 2
    return f


def abrir_y_leer(ruta, args, extra=()):
    vol = Volumen(ruta)
    N, H, W = vol.forma
    print(f"      segmento {vol.segmento}: {N} capas x {H} filas x {W} columnas ({vol.tipo}, {vol.interno})")
    delante, d1 = ajustar_capas(args.delante, N)
    detras, _ = ajustar_capas(args.detras, N)
    if d1:
        print(f"      el volumen tiene {N} capas (no 31): desplazo las capas {d1:+d} -> delante {delante}, detrás {detras}")
    if not delante or not detras:
        vol.cerrar()
        raise ValueError(f"Las capas pedidas no existen en este volumen ({N} capas).")
    centro = delante[len(delante) // 2]
    inverso = [2 * centro - c for c in detras]
    lado_a, lado_b = lados_vecinos(centro)
    todas = [c for c in set(delante + detras + inverso + lado_a + lado_b + list(extra)) if 0 <= c < N]
    f = elegir_reduccion(H, W, args.reduccion)
    if f > 1:
        print(f"      segmento grande: trabajo a 1/{f} de resolución para no agotar la memoria")
    print(f"      leyendo capas {min(todas)}-{max(todas)} (delante {delante}, detrás {detras}, control inverso {sorted(inverso)})")
    t0 = time.time()
    pila, idx = vol.leer_pila(todas, f)
    vol.cerrar()
    info = dict(vol=vol, N=N, H=H, W=W, delante=delante, detras=detras, inverso=[c for c in inverso if c in idx],
                centro=centro, lado_a=[c for c in lado_a if c in idx], lado_b=[c for c in lado_b if c in idx],
                f=f, t_lect=time.time() - t0)
    return pila, idx, info


def media_capas(pila, idx, capas):
    cs = [idx[c] for c in capas if c in idx]
    return pila[cs].astype(np.float32).mean(axis=0)


def analizar(ruta, args):
    t0 = time.time()
    total = 6
    print("\n" + "=" * 70)
    print("Segmento:", ruta)
    print("=" * 70, flush=True)
    paso(1, total, "Abriendo el segmento (sin descomprimir el zip entero)...")
    paso(2, total, "Leyendo solo las capas necesarias...")
    pila, idx, I = abrir_y_leer(ruta, args)
    vol, N, H, W, f = I["vol"], I["N"], I["H"], I["W"], I["f"]
    delante, detras, centro = I["delante"], I["detras"], I["centro"]
    fr = media_capas(pila, idx, delante)
    bk = media_capas(pila, idx, detras)
    bk_inv = media_capas(pila, idx, I["inverso"]) if I["inverso"] else bk
    ce = pila[idx[centro]].astype(np.float32)

    paso(3, total, "Máscara del papiro (vóxeles no nulos), bordes y agujeros...")
    usadas = [idx[c] for c in delante + detras]
    minimo = pila[usadas].min(axis=0)
    m = (minimo > 0).astype(np.float32)
    cobertura = float((pila.max(axis=0) > 0).mean())
    if m.mean() < 0.001:
        raise ValueError("El segmento está prácticamente vacío (todo ceros) en esas capas.")
    rb = max(1, int(round(MARGEN_BORDE / f)))
    frac = suma_caja(m, rb) / float((2 * rb + 1) ** 2)
    interior = (frac >= 0.999) & (m > 0)
    m_in = interior.astype(np.float32)
    mb_ = m > 0
    dist = ndi.distance_transform_edt(mb_) if ndi is not None else None

    paso(4, total, "Calculando los cuatro mapas (densidad, textura, capas, crujido)...")
    R = max(8, int(round(RADIO_FONDO / f)))
    rs = max(1, int(round(3 / f)))
    s = suavizar(fr, m, rs)
    z_dens = puntuacion_z(s, m, R)
    PROG.poner(0.2)
    g = suavizar(fr, m, max(1, int(round(2 / f))))
    gy, gx = np.gradient(g)
    gy *= m; gx *= m
    rt = max(2, int(round(10 / f)))
    jxx = media_mascara(gx * gx, m, rt); jyy = media_mascara(gy * gy, m, rt); jxy = media_mascara(gx * gy, m, rt)
    del gx, gy, g
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-3)
    del jxx, jyy, jxy
    z_coh = puntuacion_z((1.0 - np.clip(coh, 0, 1)) * m, m, R)
    del coh
    rl = max(2, int(round(8 / f)))
    mu = media_mascara(fr, m, rl)
    desv = np.sqrt(np.maximum(media_mascara(fr * fr, m, rl) - mu * mu, 0)) * m
    del mu
    z_std = puntuacion_z(desv, m, R)
    del desv
    z_text = (0.5 * (z_coh + z_std)).astype(np.float32)
    del z_coh, z_std
    PROG.poner(0.6)
    z_capas = puntuacion_z(suavizar((fr - bk) * m, m, rs), m, R)
    z_capas_inv = puntuacion_z(suavizar((fr - bk_inv) * m, m, rs), m, R)
    PROG.poner(0.85)
    if args.sin_crujido:
        z_cruj = np.zeros_like(z_dens)
    else:
        alta = (fr - media_mascara(fr, m, 1)) * m
        z_cruj = puntuacion_z(media_mascara(alta * alta, m, max(2, int(round(6 / f)))) * m, m, R)
        del alta
    del bk, bk_inv

    paso(5, total, "Combinando en una puntuación, buscando manchas del tamaño de un trazo y aplicando controles...")
    pesos = dict(PESOS)
    if args.sin_crujido:
        pesos["crujido"] = 0.0
    tot = sum(pesos.values()) or 1.0
    punt = (pesos["densidad"] * np.clip(z_dens, 0, None) + pesos["textura"] * np.clip(z_text, 0, None) +
            pesos["capas"] * np.clip(z_capas, 0, None) + pesos["crujido"] * np.clip(z_cruj, 0, None)) / tot
    punt = suavizar(punt.astype(np.float32), m, max(1, int(round(4 / f)))) * m_in
    vals = punt[interior]
    umbral = max(float(np.percentile(vals, args.percentil)), 0.5) if vals.size else 1.0
    binaria = punt > umbral
    while binaria.sum() > 3_000_000 and ndi is None:
        umbral *= 1.2
        binaria = punt > umbral
    lab, n = etiquetar(binaria)
    rc = max(1, int(round(3 / f)))
    cerca_borde = (suma_caja(m_in, rc) < (2 * rc + 1) ** 2 - 0.5) & (m > 0)
    p995 = float(np.percentile(fr[interior], 99.5)) if interior.any() else 255
    tmin, tmax = args.tam_min, args.tam_max
    candidatos = []
    rechazos = {"pequeñas": 0, "grandes": 0, "borde/agujero": 0, "alargadas": 0}
    zmapas = {"densidad": z_dens, "textura": z_text, "capas": z_capas, "crujido": z_cruj}
    for i, sl in enumerate(objetos(lab, n) if n else [], start=1):
        if sl is None:
            continue
        hh = (sl[0].stop - sl[0].start) * f
        ww = (sl[1].stop - sl[1].start) * f
        tam = max(hh, ww)
        if tam < tmin:
            rechazos["pequeñas"] += 1; continue
        if tam > tmax:
            rechazos["grandes"] += 1; continue
        sub = lab[sl] == i
        area = int(sub.sum()) * f * f
        if area < 0.12 * hh * ww or min(hh, ww) < 0.15 * tam:
            rechazos["alargadas"] += 1; continue
        if cerca_borde[sl][sub].any():
            rechazos["borde/agujero"] += 1; continue
        yy, xx = np.nonzero(sub)
        fila = (sl[0].start + yy.mean()) * f
        col = (sl[1].start + xx.mean()) * f
        ry = max(1, int(tam / f))
        y0, y1 = max(0, int(fila / f) - ry), min(m.shape[0], int(fila / f) + ry + 1)
        x0, x1 = max(0, int(col / f) - ry), min(m.shape[1], int(col / f) + ry + 1)
        if m[y0:y1, x0:x1].mean() < 0.98:
            rechazos["borde/agujero"] += 1; continue
        pv = punt[sl][sub]
        c = {"fila": int(round(fila)), "col": int(round(col)), "alto": int(hh), "ancho": int(ww),
             "tam": int(tam), "area": area, "media": float(pv.mean()), "pico": float(pv.max())}
        for k, M in zmapas.items():
            c[k] = float(M[sl][sub].mean())
        c["mapas"] = [k for k in zmapas if c[k] > 1.5] or [max(zmapas, key=lambda k: c[k])]
        controles(c, sl, sub, pila, idx, f, fr, mb_, dist, p995, z_capas, z_capas_inv,
                  I["lado_a"], I["lado_b"], delante)
        candidatos.append(c)
    candidatos.sort(key=lambda c: (c["media"] * math.sqrt(c["area"]), c["pico"]), reverse=True)
    agrupar(candidatos)
    for k, c in enumerate(candidatos, 1):
        c["n"] = k
        clasificar(c)
    print(f"      {n} manchas sobre el umbral {umbral:.2f}; {len(candidatos)} con tamaño de trazo "
          f"({tmin}-{tmax} px) lejos de bordes y agujeros")
    del pila

    paso(6, total, "Guardando informe y mapas...")
    salida = Path(args.salida) if args.salida else CARPETA_PROGRAMA / NOMBRE_RESULTADOS
    salida.mkdir(parents=True, exist_ok=True)
    seg = vol.segmento
    res = {
        "ruta": Path(ruta), "segmento": seg, "forma": (N, H, W), "tipo": vol.tipo, "interno": vol.interno,
        "delante": delante, "detras": detras, "inverso": I["inverso"], "lado_a": I["lado_a"], "lado_b": I["lado_b"],
        "centro": centro, "f": f, "cobertura": cobertura,
        "interior": float(interior.mean()), "umbral": umbral, "n_manchas": int(n), "rechazos": rechazos,
        "candidatos": candidatos, "pesos": pesos, "t_lect": I["t_lect"], "tam": tam_en_disco(ruta),
        "salida": salida, "args": args, "trozos": vol.trozos,
    }
    capa = ce * m
    png_mapa = salida / f"MCSerDeLuz-mapa-tinta-{seg}.png"
    png_cand = salida / f"MCSerDeLuz-candidatos-tinta-{seg}.png"
    txt = salida / f"MCSerDeLuz-informe-tinta-{seg}.txt"
    csvp = salida / f"MCSerDeLuz-candidatos-tinta-{seg}.csv"
    fig = figura_mapas(res, capa, m, z_dens, z_text, z_capas, z_cruj, punt)
    fig.savefig(png_mapa, dpi=args.dpi)
    fig2 = figura_candidatos(res, capa, punt, m)
    if fig2 is not None:
        fig2.savefig(png_cand, dpi=args.dpi)
    elif png_cand.exists():
        png_cand.unlink()
    res["t_total"] = time.time() - t0
    escribir_informe(txt, res, png_mapa, png_cand if fig2 is not None else None, csvp)
    escribir_csv(csvp, candidatos[: max(args.max_candidatos, 50)])
    if getattr(args, "exportar_recortes", False) and candidatos:
        res["recortes"] = str(exportar_recortes(salida, seg, ce, punt, candidatos[: args.max_candidatos], f,
                                                f"capa {centro}", "puntuación combinada", max(umbral * 1.6, 1.0),
                                                mascara=m > 0)[0])
    res.update({"png_mapa": png_mapa, "png_cand": png_cand if fig2 is not None else None, "txt": txt,
                "csv": csvp, "fig": fig, "fig2": fig2})
    print(f"      informe:    {txt}")
    print(f"      mapa:       {png_mapa}")
    if fig2 is not None:
        print(f"      candidatos: {png_cand}")
    print(f"      tiempo: {res['t_total']:.0f} s", flush=True)
    return res


# ====================================================================================
#  BARRIDO DE PHerc 1447: datos públicos del Vesuvius Challenge
#  (descarga con conexiones persistentes, reintentos y reanudación: idea de fls.py de
#   Matteo Bulloni, licencia MIT)
# ====================================================================================
BUCKET_HOST = "vesuvius-challenge-open-data.s3.amazonaws.com"
PREFIJO_1447 = "PHerc1447/segments/"
CATALOGO_1447 = {  # respaldo sin internet: tamaño total del zarr (bytes) a 31-10-2026
    "20250502180708-auto_grown_20250502160708188": 57178992, "20250502180748-auto_grown_20250502160748721": 115068765,
    "20250502182142-auto_grown_20250502161324419": 156223868, "20250502182456-auto_grown_20250502161202782": 208142175,
    "20250502183138-auto_grown_20250502162038685": 100271565, "20250502183421-auto_grown_20250502161744358": 172634278,
    "20250502184201-auto_grown_20250502163549332": 145000380, "20250502184658-auto_grown_20250502163923577": 179651933,
    "20250502184845-auto_grown_20250502164121265": 241024989, "20250502185519-auto_grown_20250502164303733": 175491980,
    "20250502205333-auto_grown_20250502181030065": 280156102, "20250702235910-auto_grown_20250702235910292": 183521673,
    "20250703025628-auto_grown_20250703025628283": 308052438, "20250703034159-auto_grown_20250703034159599": 344952180,
    "20251105093211-z_dbg_gen_00320": 342951919,
}
import threading, http.client, ssl, urllib.parse
_tls = threading.local()


def bucket_get(ruta, intentos=6):
    """GET sobre una conexión HTTPS persistente por hilo; None si 404 (adaptado de fls.py, Bulloni, MIT)."""
    for a in range(intentos):
        c = getattr(_tls, "c", None)
        if c is None:
            c = _tls.c = http.client.HTTPSConnection(BUCKET_HOST, timeout=60, context=ssl.create_default_context())
        try:
            c.request("GET", ruta, headers={"User-Agent": "MCSerDeLuz-buscar-tinta"})
            r = c.getresponse(); b = r.read()
            if r.status == 200:
                return b
            if r.status == 404:
                return None
            raise IOError(f"HTTP {r.status}")
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            _tls.c = None
            time.sleep(0.5 + a)
    raise IOError(f"no consigo descargar {ruta} (¿hay conexión a internet?)")


def s3_listar(prefijo, delim=None):
    claves, prefijos, tok = [], [], None
    while True:
        q = {"list-type": "2", "prefix": prefijo}
        if delim:
            q["delimiter"] = delim
        if tok:
            q["continuation-token"] = tok
        t = bucket_get("/?" + urllib.parse.urlencode(q))
        if t is None:
            break
        t = t.decode("utf-8", "replace")
        claves += [(k, int(s)) for k, s in re.findall(r"<Key>([^<]*)</Key>.*?<Size>(\d+)</Size>", t, re.S)]
        prefijos += re.findall(r"<CommonPrefixes><Prefix>([^<]*)</Prefix>", t)
        m = re.search(r"<NextContinuationToken>([^<]*)<", t)
        if not m:
            break
        tok = m.group(1)
    return claves, prefijos


def write_atomic(path, data):
    tmp = f"{path}.part{os.getpid()}_{threading.get_ident()}"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def carpeta_cache(args):
    if args.cache:
        return Path(args.cache)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    return Path(base) / "MCSerDeLuz" / "cache-PHerc1447"


def catalogo_1447(cache, usar_red=True):
    """Lista los segmentos de PHerc 1447 del bucket público, con el tamaño de su zarr."""
    cache.mkdir(parents=True, exist_ok=True)
    fich = cache / "catalogo-PHerc1447.json"
    if fich.exists() and time.time() - fich.stat().st_mtime < 86400:
        try:
            return json.loads(fich.read_text("utf-8")), "caché"
        except Exception:
            pass
    if usar_red:
        try:
            _, segs = s3_listar(PREFIJO_1447, "/")
            segs = [p for p in segs if re.match(r".*/\d{14}", p)]
            from concurrent.futures import ThreadPoolExecutor

            def uno(p):
                _, zs = s3_listar(p + "surface-volumes/", "/")
                zs = [z for z in zs if z.rstrip("/").endswith(".zarr")]
                if not zs:
                    return None
                z = zs[0]
                claves, _ = s3_listar(z)
                n0 = [(k, s) for k, s in claves if k[len(z):].startswith("0/")]
                return {"seg": p[len(PREFIJO_1447):].rstrip("/"), "zarr": z, "total": sum(s for _, s in claves),
                        "nivel0": sum(s for _, s in n0), "trozos0": len(n0)}
            with ThreadPoolExecutor(8) as ex:
                cat = [r for r in ex.map(uno, segs) if r]
            write_atomic(fich, json.dumps(cat, indent=1).encode("utf-8"))
            return cat, "internet"
        except Exception as e:
            print(f"      (no puedo leer la lista en internet: {e}; uso la lista guardada)")
    vol = "8.64um-1.2m-116keV-volume-20250521151220.zarr/"
    return [{"seg": s, "zarr": f"{PREFIJO_1447}{s}/surface-volumes/{vol}", "total": t, "nivel0": int(t * 0.75),
             "trozos0": None} for s, t in CATALOGO_1447.items()], "lista guardada"


def descargar_nivel(entrada, cache, nivel):
    """Descarga (o reanuda) un nivel del zarr del segmento a la caché. Devuelve la carpeta del segmento."""
    z = entrada["zarr"]
    dest_seg = cache / entrada["seg"]
    dest_z = dest_seg / "surface-volumes" / z.rstrip("/").split("/")[-1]
    claves, _ = s3_listar(z + f"{nivel}/")
    extra = [(z + n, 0) for n in (".zgroup", ".zattrs")]
    claves = extra + claves
    pend = []
    for k, s in claves:
        p = dest_z / k[len(z):]
        if p.exists() and (s == 0 or p.stat().st_size == s):
            continue
        pend.append((k, s, p))
    total = sum(s for _, s, _ in pend)
    if pend:
        print(f"      descargando nivel {nivel}: {len(pend)} archivos, {mb(total)} ...", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    hecho = [0, 0, -1]
    cerrojo = threading.Lock()

    def uno(t):
        k, s, p = t
        b = bucket_get("/" + urllib.parse.quote(k))
        if b is None:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(p, b)
        with cerrojo:
            hecho[0] += len(b); hecho[1] += 1
            pct = int(100 * hecho[0] / max(total, 1))
            if total > 5e6 and pct // 10 != hecho[2] // 10:
                hecho[2] = pct
                print(f"      ... {pct:3d} %  ({mb(hecho[0])})", flush=True)

    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(uno, t) for t in pend]
        from concurrent.futures import wait, FIRST_EXCEPTION
        while True:
            hechos, quedan = wait(futs, timeout=0.5, return_when=FIRST_EXCEPTION)
            PROG.poner(hecho[0] / max(total, 1), f"descargando {entrada['seg'][:14]} (nivel {nivel})...")
            if not quedan or any(f_.exception() for f_ in hechos):
                break
        for f_ in futs:
            f_.result()
    return dest_seg, hecho[0]


def cobertura_rapida(carpeta):
    """% de papiro estimado con el nivel 4 (1/16), para no descargar segmentos casi vacíos."""
    v = Volumen(carpeta, nivel="4")
    try:
        pila, _ = v.leer_pila(range(v.forma[0]), 1)
        return float((pila.max(axis=0) > 0).mean())
    finally:
        v.cerrar()


def analizar_barrido_segmento(ruta, args, salida, seg_nombre, tam_mb, origen):
    """Mapas del barrido (densidad, pérdida de fibra, textura std, entre capas, crackle), umbral z>4,
    manchas de 25-160 px a más de 45 px de bordes y agujeros, sin huecos oscuros, y controles."""
    t0 = time.time()
    A = argparse.Namespace(**vars(args))
    A.delante, A.detras = [14, 15, 16], [17, 18, 19, 20]
    PROG.fase(0.5 if origen.startswith("internet") else 0.0, 0.6 if origen.startswith("internet") else 0.2, "leyendo capas 10-21...")
    pila, idx, I = abrir_y_leer(ruta, A, extra=range(10, 22))
    PROG.fase(0.6 if origen.startswith("internet") else 0.2, 0.97, "calculando mapas del barrido...")
    f = I["f"]
    seg = I["vol"].segmento
    L = lambda c: pila[idx[c]].astype(np.float32)
    capas_mask = [c for c in range(14, 21) if c in idx]
    m0 = (pila[[idx[c] for c in capas_mask]] > 0).all(axis=0)
    papiro = float((pila[[idx[c] for c in range(10, 22) if c in idx]].max(axis=0) > 0).mean())
    out = dict(seg=seg, nombre=seg_nombre, mb=tam_mb, origen=origen, H=I["H"], W=I["W"], f=f, papiro=papiro,
               candidatos=[], estado="ok")
    if papiro < args.min_papiro / 100:
        out["estado"] = f"omitido: solo {papiro * 100:.1f} % de papiro (< {args.min_papiro:g} %)"
        return out, None
    print("      calculando mapas del barrido...", flush=True)
    m0 = limpiar_mascara(m0, f)
    dist = ndi.distance_transform_edt(m0) if ndi is not None else None
    core = (dist > 45 / f) if dist is not None else erosionar(m0, int(45 / f))
    out["nucleo"] = float(core.mean())
    if core.sum() < 1000:
        out["estado"] = "omitido: casi todo es borde o agujero"
        return out, None
    s_ = lambda v: v / f
    S = (L(14) + L(15) + L(16)) / 3
    B = (L(17) + L(18) + L(19) + L(20)) / 4
    Brev = (L(10) + L(11) + L(12) + L(13)) / 4      # control: orden de profundidad invertido
    maps = {}
    maps["densidad"] = zG(G(bgsub(S, m0, s_(50)), s_(6)), core, s_(150))
    PROG.poner(1/7)
    hp = bgsub(S, m0, s_(8))
    gx, gy = sobel(G(S, s_(1.5)))
    J11 = G(gx * gx, s_(10)); J22 = G(gy * gy, s_(10)); J12 = G(gx * gy, s_(10))
    del gx, gy
    coh = np.sqrt((J11 - J22) ** 2 + 4 * J12 ** 2) / (J11 + J22 + 1e-3)
    del J11, J22, J12
    maps["perdida_fibra"] = zG(G(-coh, s_(4)), core, s_(150)); del coh
    PROG.poner(2/7)
    maps["textura_std"] = zG(np.sqrt(G(hp * hp, s_(10))), core, s_(150)); del hp
    PROG.poner(3/7)
    maps["entre_capas"] = zG(G(bgsub(S - B, m0, s_(50)), s_(6)), core, s_(150))
    PROG.poner(4/7)
    inv = zG(G(bgsub(S - Brev, m0, s_(50)), s_(6)), core, s_(150))
    PROG.poner(6/7)
    maps["crackle"] = zG(G(np.abs(S - G(S, s_(1.5))), s_(6)), core, s_(150))
    PROG.poner(5/7)
    Sm = G(S, s_(4))
    hueco = float(np.percentile(Sm[core], 10))
    p995 = float(np.percentile(S[core], 99.5))
    brutos = []
    for k, M in maps.items():
        lab, n = etiquetar((M > args.z_umbral) & core)
        for i, sl in enumerate(objetos(lab, n) if n else [], start=1):
            if sl is None:
                continue
            reg = lab[sl] == i
            area = int(reg.sum()) * f * f
            h = (sl[0].stop - sl[0].start) * f
            w = (sl[1].stop - sl[1].start) * f
            if area < 300 or max(h, w) > 160 or max(h, w) < 25:
                continue
            if Sm[sl][reg].mean() < hueco:   # hueco oscuro: no es papiro
                continue
            sub = M[sl] * reg
            pk = np.unravel_index(np.argmax(sub), sub.shape)
            brutos.append(dict(mapa=k, fila=int((sl[0].start + pk[0]) * f), col=int((sl[1].start + pk[1]) * f),
                               alto=int(h), ancho=int(w), tam=int(max(h, w)), area=area, z=float(sub.max()),
                               _sl=sl, _reg=reg))
    # la misma mancha vista por varios mapas cuenta una vez
    brutos.sort(key=lambda c: -c["z"])
    cands = []
    for c in brutos:
        for d in cands:
            if math.hypot(c["fila"] - d["fila"], c["col"] - d["col"]) < 30:
                if c["mapa"] not in d["mapas"]:
                    d["mapas"].append(c["mapa"])
                break
        else:
            c["mapas"] = [c["mapa"]]
            cands.append(c)
    for c in cands:
        controles(c, c["_sl"], c["_reg"], pila, idx, f, S, m0, dist, p995, maps["entre_capas"], inv,
                  I["lado_a"], I["lado_b"], [14, 15, 16])
    agrupar(cands)
    for n_, c in enumerate(cands, 1):
        c["n"] = n_
        clasificar(c)
        c.pop("_sl"); c.pop("_reg")
    out["candidatos"] = cands
    out["por_mapa"] = {k: sum(k in c["mapas"] for c in cands) for k in maps}
    out["por_tipo"] = {t: sum(c["tipo"] == t for c in cands) for t in TIPOS}
    out["t"] = time.time() - t0
    # figura del segmento
    comb = np.max(np.stack([np.clip(M, 0, None) for M in maps.values()]), 0)
    vista = dict(capa=L(15), m0=m0, comb=np.where(core, comb, np.nan))
    png = salida / f"MCSerDeLuz-barrido-{seg}.png"
    figura_barrido_segmento(out, vista, png, args.dpi)
    out["png"] = str(png)
    if getattr(args, "exportar_recortes", False) and cands:
        out["recortes"] = str(exportar_recortes(salida, seg, L(15), comb, cands, f, "capa 15",
                                                "máximo z de los cinco mapas", 8, mascara=m0)[0])
    k = max(1, int(math.ceil(max(S.shape) / 600)))
    mini = L(15)[::k, ::k]
    return out, (mini, k * f)


def figura_barrido_segmento(out, v, png, dpi):
    capa, m0, comb = v["capa"], v["m0"], v["comb"]
    f = out["f"]
    h, w = capa.shape
    ext = (0, w * f, h * f, 0)
    fig, ax = plt.subplots(1, 2, figsize=(18, 9 * h / w + 1.4))
    lo, hi = np.percentile(capa[m0], [1, 99.5]) if m0.any() else (0, 255)
    ax[0].imshow(capa, cmap="gray", vmin=lo, vmax=hi, extent=ext)
    ax[0].set_title(f"{out['seg']} capa 15")
    ax[1].imshow(comb, cmap="magma", vmin=0, vmax=8, extent=ext)
    ax[1].set_title("máximo z (densidad, pérdida de fibra, textura, entre capas, crackle)")
    for A in ax:
        for c in out["candidatos"][:60]:
            A.add_patch(Circle((c["col"], c["fila"]), 45, fill=False, ec=TIPOS[c["tipo"]][1], lw=1.3))
        for c in out["candidatos"][:5]:
            A.text(c["col"] + 50, c["fila"], str(c["n"]), color="white", fontsize=11, weight="bold")
        A.set_xticks([]); A.set_yticks([])
    ley = LEYENDA
    fig.suptitle(f"PHerc 1447 {out['seg']} — {len(out['candidatos'])} candidatos (z>4, 25-160 px). Colores: {ley}. "
                 "Pistas débiles, no pruebas.", fontsize=10)
    fig.tight_layout()
    fig.savefig(png, dpi=dpi)
    plt.close(fig)


def barrido(args, encontrados):
    """Barrido por lotes de los segmentos oficiales pequeños de PHerc 1447."""
    t0 = time.time()
    salida = (Path(args.salida) if args.salida else CARPETA_PROGRAMA) / "MCSerDeLuz-barrido-PHerc1447"
    salida.mkdir(parents=True, exist_ok=True)
    cache = carpeta_cache(args)
    print("\n" + "=" * 70)
    print(f"BARRIDO PHerc 1447: segmentos de {args.limite_mb:g} MB o menos, capas 10-21, sin IA")
    print(f"Resultados: {salida}")
    if not args.sin_descargas:
        print(f"Descargas:  {cache}  (unos 100 MB por segmento que no tengas; puedes borrar esa carpeta luego)")
    print("=" * 70, flush=True)
    cat, fuente = catalogo_1447(cache, usar_red=not args.sin_descargas)
    print(f"Lista de segmentos ({fuente}): {len(cat)}")
    locales = {id_segmento(p): p for p in encontrados}
    filas, minis = [], {}
    lista = [e for e in sorted(cat, key=lambda e: e["total"])
             if e["total"] / 1e6 <= args.limite_mb or id_segmento(e["seg"]) in locales]
    for i_seg, e in enumerate(lista):
        sid = id_segmento(e["seg"])
        tmb = e["total"] / 1e6
        local = locales.get(sid)
        PROG.tramo(i_seg / len(lista), (i_seg + 1) / len(lista))
        PROG.poner(0.0, f"segmento {i_seg + 1} de {len(lista)}: {sid}")
        print(f"\n--- {sid}  ({tmb:.0f} MB{', LOCAL' if local else ''}) ---", flush=True)
        fres = salida / f"res_{sid}.json"
        if fres.exists() and not args.rehacer:
            try:
                r = json.loads(fres.read_text("utf-8"))
                print("      ya analizado antes (uso el resultado guardado; --rehacer para repetir)")
                fm = salida / f"vista_{sid}.npz"
                if fm.exists():
                    try:
                        z_ = np.load(fm)
                        minis[sid] = (z_["mini"], int(z_["k"]))
                    except Exception:
                        pass
                filas.append(r); continue
            except Exception:
                pass
        try:
            if local:
                ruta, origen = local, "zip local" if str(local).lower().endswith(".zip") else "carpeta local"
            elif args.sin_descargas:
                print("      no lo tengo y has elegido no descargar: lo salto")
                filas.append(dict(seg=sid, nombre=e["seg"], mb=tmb, origen="-", papiro=None, candidatos=[],
                                  estado="saltado: no está en el ordenador")); continue
            else:
                PROG.fase(0.0, 0.03)
                carpeta, _ = descargar_nivel(e, cache, 4)
                cov = cobertura_rapida(carpeta)
                print(f"      papiro estimado (nivel 4): {cov * 100:.1f} %")
                if cov < args.min_papiro / 100:
                    filas.append(dict(seg=sid, nombre=e["seg"], mb=tmb, origen="internet", papiro=cov, candidatos=[],
                                      estado=f"omitido: solo {cov * 100:.1f} % de papiro (< {args.min_papiro:g} %)"))
                    continue
                if e.get("nivel0"):
                    print(f"      nivel 0 (resolución completa): {mb(e['nivel0'])} a descargar como máximo")
                PROG.fase(0.03, 0.5)
                ruta, _ = descargar_nivel(e, cache, 0)
                origen = "internet (caché)"
            r, mini = analizar_barrido_segmento(ruta, args, salida, e["seg"], tmb, origen)
            if mini is not None:
                minis[sid] = mini
                np.savez_compressed(salida / f"vista_{sid}.npz", mini=mini[0].astype(np.uint8), k=mini[1])
            print(f"      {r['estado']}: {len(r['candidatos'])} candidatos " +
                  (str(r.get("por_tipo", "")) if r["candidatos"] else ""), flush=True)
            write_atomic(fres, json.dumps(r, indent=1, ensure_ascii=False).encode("utf-8"))
            filas.append(r)
        except KeyboardInterrupt:
            raise
        except MemoryError:
            filas.append(dict(seg=sid, nombre=e["seg"], mb=tmb, origen="-", papiro=None, candidatos=[],
                              estado="error: sin memoria (prueba --reduccion 2)"))
        except Exception as ex:
            print(f"      ERROR: {type(ex).__name__}: {ex}")
            filas.append(dict(seg=sid, nombre=e["seg"], mb=tmb, origen="-", papiro=None, candidatos=[],
                              estado=f"error: {type(ex).__name__}: {ex}"))
    PROG.tramo(0, 1); PROG.poner(1.0, "barrido terminado")
    escribir_resumen_barrido(salida, filas, args, time.time() - t0)
    png = figura_resumen_barrido(salida, filas, minis, args.dpi)
    return salida, filas, png


def escribir_resumen_barrido(salida, filas, args, t):
    txt = salida / "MCSerDeLuz-barrido-PHerc1447-resumen.txt"
    csv1 = salida / "MCSerDeLuz-barrido-PHerc1447-resumen.csv"
    csv2 = salida / "MCSerDeLuz-barrido-PHerc1447-candidatos.csv"
    tipo_txt = lambda r: ", ".join(f"{TIPOS[t][0]} {n}" for t, n in (r.get("por_tipo") or {}).items() if n) or "-"
    L = ["MCSerDeLuz - BARRIDO SIN IA DE PHerc 1447 (segmentos pequeños)", "=" * 78,
         f"Fecha: {datetime.datetime.now():%Y-%m-%d %H:%M}   Programa: buscar_tinta_papiro.py v{VERSION}   Tiempo: {t / 60:.1f} min",
         f"Criterios: segmentos <= {args.limite_mb:g} MB (y los que ya tienes en el ordenador), capas 10-21, "
         f"papiro >= {args.min_papiro:g} %,", f"           z > {args.z_umbral:g}, manchas de 25-160 px, a más de 45 px de bordes y agujeros, sin huecos oscuros.",
         "", f"{'segmento':<15} {'MB':>5} {'papiro':>7} {'cand.':>5}  qué son / estado", "-" * 78]
    for r in filas:
        pap = f"{r['papiro'] * 100:.1f}%" if r.get("papiro") is not None else "-"
        est = tipo_txt(r) if r.get("estado") == "ok" else r.get("estado", "")
        L.append(f"{r['seg']:<15} {r['mb']:>5.0f} {pap:>7} {len(r['candidatos']):>5}  {est}")
    L += ["", "MEJORES CANDIDATOS DE CADA SEGMENTO (fila, columna en px del segmento)", "-" * 78]
    for r in filas:
        for c in r["candidatos"][:5]:
            L.append(f"{r['seg']}  #{c['n']:<3} ({c['fila']},{c['col']})  {c['alto']}x{c['ancho']} px  "
                     f"z={c['z']:.1f}  mapas: {'+'.join(c['mapas'])}  ->  {c['que_es']}  "
                     f"[superficie {c['sup']:+.1f}, vecinas {c['vec_a']:+.1f}/{c['vec_b']:+.1f}, "
                     f"directo {c['fwd']:+.1f} / inverso {c['rev']:+.1f}, borde {c['dist_borde']} px]")
    trazos = sum(c["tipo"] == "trazo" for r in filas for c in r["candidatos"])
    L += ["", "VEREDICTO AUTOMÁTICO", "-" * 78,
          (f"{trazos} candidatos 'grupo tipo trazo' (agrupados, solo en la superficie y más fuertes en el orden directo "
           "que en el inverso). Son los únicos que merece la pena mirar a mano, con el modelo de tinta y en las capas vecinas."
           if trazos else "Ningún candidato pasa los controles como 'grupo tipo trazo': todo se explica mejor por granos, "
           "fibras, separación de capas o motas."), "",
          "QUÉ SIGNIFICA CADA TIPO", "-" * 78,
          "grano brillante / inclusión: también se ve en las capas de ambos lados o está saturado (objeto denso en 3D).",
          "fibra o separación de capas: alargado, o solo en pérdida de fibra / entre capas, o igual en el orden inverso.",
          "motas sueltas: puntos pequeños de alta frecuencia (crackle) o manchas diminutas.",
          "grupo tipo trazo: varias manchas a menos de 250 px, solo en la superficie, más fuertes en el orden directo.",
          "aislado, sin explicar: no encaja en lo anterior; solo y aislado casi nunca es escritura.",
          "", "CONTROLES (adaptados de first-letters-survey, Matteo Bulloni, MIT): contraste de la mancha frente a su anillo en cada",
          "capa 10-21 (capas vecinas), orden de profundidad invertido (14-16 menos 10-13 frente a 14-16 menos 17-20) y",
          "distancia a bordes y agujeros de la malla.", "",
          "AVISO: la tinta de carbono casi no cambia la densidad del papiro. Esto son PISTAS DÉBILES, no pruebas de escritura.",
          "", f"Tablas: {csv1.name} y {csv2.name}. Imágenes: MCSerDeLuz-barrido-<segmento>.png y MCSerDeLuz-barrido-PHerc1447.png"]
    with open(txt, "w", encoding="utf-8-sig", newline="\r\n" if os.name == "nt" else "\n") as fh:
        fh.write("\n".join(L) + "\n")
    with open(csv1, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["segmento", "nombre", "MB", "origen", "papiro_%", "candidatos", "granos", "fibras", "motas",
                    "tipo_trazo", "aislados", "estado", "top3"])
        for r in filas:
            pt = r.get("por_tipo") or {}
            w.writerow([r["seg"], r.get("nombre", ""), f"{r['mb']:.0f}", r.get("origen", ""),
                        f"{r['papiro'] * 100:.1f}".replace(".", ",") if r.get("papiro") is not None else "",
                        len(r["candidatos"]), pt.get("grano", 0), pt.get("fibra", 0), pt.get("motas", 0),
                        pt.get("trazo", 0), pt.get("aislado", 0), r.get("estado", ""),
                        "; ".join(f"({c['fila']},{c['col']}) {c['alto']}x{c['ancho']}px {'+'.join(c['mapas'])} "
                                  f"z={c['z']:.1f} {c['que_es']}" for c in r["candidatos"][:3])])
    with open(csv2, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["segmento", "n", "fila", "columna", "alto_px", "ancho_px", "area_px", "z", "mapas", "que_es",
                    "superficie", "vecinas_10_12", "vecinas_19_21", "directo", "inverso", "saturado", "alargamiento",
                    "vecinos_250px", "dist_borde_px"])
        for r in filas:
            for c in r["candidatos"]:
                w.writerow([r["seg"], c["n"], c["fila"], c["col"], c["alto"], c["ancho"], c["area"],
                            f"{c['z']:.2f}".replace(".", ","), "+".join(c["mapas"]), c["que_es"],
                            *[f"{c[k]:.2f}".replace(".", ",") for k in ("sup", "vec_a", "vec_b", "fwd", "rev", "saturado", "elong")],
                            c["vecinos"], c["dist_borde"]])
    print(f"\nResumen: {txt}\nTablas:  {csv1}\n         {csv2}")


def figura_resumen_barrido(salida, filas, minis, dpi):
    hechos = [r for r in filas if r["seg"] in minis]
    if not hechos:
        return None
    cols = min(4, len(hechos))
    nf = int(math.ceil(len(hechos) / cols))
    fig, ejes = plt.subplots(nf, cols, figsize=(5.5 * cols, 5.8 * nf), squeeze=False)
    try:
        fig.canvas.manager.set_window_title("MCSerDeLuz - barrido PHerc 1447")
    except Exception:
        pass
    for a in ejes.ravel():
        a.axis("off")
    for a, r in zip(ejes.ravel(), hechos):
        mini, k = minis[r["seg"]]
        v = mini[mini > 0]
        lo, hi = np.percentile(v, [1, 99.5]) if v.size else (0, 255)
        a.imshow(mini, cmap="gray", vmin=lo, vmax=hi, extent=(0, mini.shape[1] * k, mini.shape[0] * k, 0))
        for c in r["candidatos"][:60]:
            a.add_patch(Circle((c["col"], c["fila"]), 60, fill=False, ec=TIPOS[c["tipo"]][1], lw=1.2))
        a.set_title(f"{r['seg']}  {r['mb']:.0f} MB  papiro {r['papiro'] * 100:.0f}%  cand. {len(r['candidatos'])}", fontsize=10)
    ley = LEYENDA
    fig.suptitle("MCSerDeLuz — barrido sin IA de PHerc 1447 (capa 15). " + ley + ". Pistas débiles, no pruebas.", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    png = salida / "MCSerDeLuz-barrido-PHerc1447.png"
    fig.savefig(png, dpi=dpi)
    return fig


# ====================================================================================
#  RECORTES DE CADA CANDIDATO (--exportar-recortes)
# ====================================================================================
def exportar_recortes(base, seg, capa, mapa, cands, f, nombre_capa, nombre_mapa, vmax, dpi=120, mascara=None):
    """Guarda un PNG por candidato: capa de papiro y mapa de anomalía alrededor, con escala y coordenadas."""
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    dest = Path(base) / f"MCSerDeLuz-recortes-{seg}"
    dest.mkdir(parents=True, exist_ok=True)
    for viejo in dest.glob("MCSerDeLuz-recorte-*.png"):
        try:
            viejo.unlink()
        except Exception:
            pass
    if mascara is not None and mascara.any():
        lo, hi = np.percentile(capa[mascara], [1, 99.5])
    else:
        lo, hi = float(np.nanmin(capa)), float(np.nanmax(capa))
    mm_px = 1000.0 / TAM_PIXEL_UM                      # 1 mm en píxeles del segmento (~116)
    hechos = []
    for c in cands:
        mitad = max(160, int(c["tam"] * 2.5))          # ventana en píxeles del segmento
        yc, xc = int(c["fila"] / f), int(c["col"] / f)
        r = max(4, int(mitad / f))
        y0, y1 = max(0, yc - r), min(capa.shape[0], yc + r)
        x0, x1 = max(0, xc - r), min(capa.shape[1], xc + r)
        if y1 - y0 < 4 or x1 - x0 < 4:
            continue
        ext = (x0 * f, x1 * f, y1 * f, y0 * f)
        fig = Figure(figsize=(11, 6.0))
        ax = fig.subplots(1, 2)
        ax[0].imshow(capa[y0:y1, x0:x1], cmap="gray", vmin=lo, vmax=hi, extent=ext, interpolation="bicubic")
        ax[0].set_title(nombre_capa, fontsize=10)
        im = ax[1].imshow(mapa[y0:y1, x0:x1], cmap="magma", vmin=0, vmax=vmax, extent=ext, interpolation="nearest")
        ax[1].set_title(nombre_mapa, fontsize=10)
        fig.colorbar(im, ax=ax[1], fraction=0.045, pad=0.02)
        color = TIPOS.get(c.get("tipo"), ("", "cyan"))[1]
        for a in ax:
            a.add_patch(Circle((c["col"], c["fila"]), max(c["tam"] * 0.75, 25), fill=False, ec=color, lw=1.5))
            a.plot([c["col"]], [c["fila"]], "+", color=color, ms=8)
            # barra de escala de 1 mm (o 0,5 mm si la ventana es pequeña)
            largo_mm = 1.0 if (x1 - x0) * f > 2.2 * mm_px else 0.5
            L_ = largo_mm * mm_px
            bx, by = x0 * f + 0.06 * (x1 - x0) * f, y1 * f - 0.08 * (y1 - y0) * f
            a.add_patch(Rectangle((bx, by), L_, max(3, 0.012 * (y1 - y0) * f), color="white", ec="black", lw=0.5))
            a.text(bx + L_ / 2, by - 0.02 * (y1 - y0) * f, f"{largo_mm:g} mm".replace(".", ","), color="white",
                   ha="center", va="bottom", fontsize=9, weight="bold")
            a.set_xlabel("columna (px)", fontsize=8); a.set_ylabel("fila (px)", fontsize=8)
            a.tick_params(labelsize=7)
        fig.suptitle(f"PHerc 1447 - segmento {seg} - candidato #{c['n']}  fila {c['fila']}, columna {c['col']}  "
                     f"({c['alto']}x{c['ancho']} px = {c['tam'] * TAM_PIXEL_UM / 1000:.2f} mm)\n"
                     f"qué es: {c.get('que_es', '-')}   |   píxel = {TAM_PIXEL_UM} µm   |   pista débil, no prueba",
                     fontsize=10)
        fig.tight_layout(rect=[0, 0.01, 1, 0.92])
        p = dest / f"MCSerDeLuz-recorte-{seg}-{c['n']:02d}.png"
        fig.savefig(p, dpi=dpi)
        hechos.append(p)
    print(f"      recortes:   {len(hechos)} PNG en {dest}")
    return dest, hechos


# ====================================================================================
#  FIGURAS
# ====================================================================================
def _estirar(x, m, p=(1, 99.5)):
    v = x[m > 0]
    if v.size == 0:
        return 0, 1
    lo, hi = np.percentile(v, p)
    return float(lo), float(hi if hi > lo else lo + 1)


def figura_mapas(res, capa, m, z_dens, z_text, z_capas, z_cruj, punt):
    N, H, W = res["forma"]
    f = res["f"]
    h, w = capa.shape
    paso_vis = max(1, int(math.ceil(max(h, w) / 2200)))
    ext = (0, w * f, h * f, 0)
    sub = (slice(None, None, paso_vis), slice(None, None, paso_vis))
    ancho = 20
    alto = ancho * (2 * h / w) / 3 * 1.05 + 1.6
    fig, ejes = plt.subplots(2, 3, figsize=(ancho, min(max(alto, 9), 22)))
    fig.canvas.manager.set_window_title(f"MCSerDeLuz - indicios de tinta - {res['segmento']}") if hasattr(fig.canvas, "manager") and fig.canvas.manager else None
    lo, hi = _estirar(capa, m)
    paneles = [
        (capa, f"Capa {res['centro']} (papiro)", "gray", lo, hi),
        (z_dens, "1. Densidad anómala (z, + = más denso)", "magma", 0, 3),
        (z_text, "2. Textura / fibras rotas (z)", "magma", 0, 3),
        (z_capas, f"3. Capas {res['delante'][0]}-{res['delante'][-1]} menos {res['detras'][0]}-{res['detras'][-1]} (z)", "magma", 0, 3),
        (z_cruj, "4. Crujido: alta frecuencia (z)", "magma", 0, 3),
        (punt, "Puntuación combinada + candidatos", "inferno", 0, max(res["umbral"] * 1.6, 1.0)),
    ]
    for a, (img, tit, cmap, vmin, vmax) in zip(ejes.ravel(), paneles):
        im = a.imshow(img[sub], cmap=cmap, vmin=vmin, vmax=vmax, extent=ext, interpolation="nearest")
        a.set_title(tit, fontsize=12)
        a.tick_params(labelsize=8)
        fig.colorbar(im, ax=a, fraction=0.035, pad=0.01)
    top = res["candidatos"][: res["args"].max_candidatos]
    for a in (ejes.ravel()[0], ejes.ravel()[5]):
        for c in top:
            r = max(c["tam"] * 0.75, 25)
            col_ = TIPOS[c["tipo"]][1]
            a.add_patch(Circle((c["col"], c["fila"]), r, fill=False, color=col_, lw=1.4))
            a.text(c["col"] + r, c["fila"] - r, str(c["n"]), color=col_, fontsize=9, fontweight="bold")
    fig.suptitle(f"MCSerDeLuz - PHerc - segmento {res['segmento']} - indicios de tinta SIN IA "
                 f"({len(res['candidatos'])} candidatos, se marcan {len(top)}). "
                 "Son pistas débiles, no pruebas.\nColores: " + LEYENDA, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def figura_candidatos(res, capa, punt, m):
    top = res["candidatos"][: min(12, res["args"].max_candidatos)]
    if not top:
        return None
    f = res["f"]
    cols = 4
    filas = int(math.ceil(len(top) / cols))
    fig, ejes = plt.subplots(filas, cols, figsize=(16, 4.2 * filas), squeeze=False)
    try:
        fig.canvas.manager.set_window_title(f"MCSerDeLuz - candidatos - {res['segmento']}")
    except Exception:
        pass
    lo, hi = _estirar(capa, m)
    for a in ejes.ravel():
        a.axis("off")
    for a, c in zip(ejes.ravel(), top):
        r = int(max(100, c["tam"] * 2) / f)
        yc, xc = int(c["fila"] / f), int(c["col"] / f)
        y0, y1 = max(0, yc - r), min(capa.shape[0], yc + r)
        x0, x1 = max(0, xc - r), min(capa.shape[1], xc + r)
        ext = (x0 * f, x1 * f, y1 * f, y0 * f)
        a.imshow(capa[y0:y1, x0:x1], cmap="gray", vmin=lo, vmax=hi, extent=ext, interpolation="bicubic")
        try:
            a.contour(np.linspace(x0 * f, x1 * f, x1 - x0), np.linspace(y0 * f, y1 * f, y1 - y0),
                      punt[y0:y1, x0:x1], levels=[res["umbral"]], colors="red", linewidths=1.0)
        except Exception:
            pass
        a.add_patch(Circle((c["col"], c["fila"]), max(c["tam"] * 0.75, 25), fill=False, color=TIPOS[c["tipo"]][1], lw=1.2))
        a.set_title(f"#{c['n']}  fila {c['fila']}, col {c['col']}\n{c['tam']} px ({c['tam'] * TAM_PIXEL_UM / 1000:.2f} mm), "
                    f"punt. {c['media']:.2f} - {c['que_es']}", fontsize=9)
        a.axis("on"); a.tick_params(labelsize=7)
    fig.suptitle(f"Segmento {res['segmento']} - capa {res['centro']} alrededor de los mejores candidatos "
                 f"(rojo = zona sobre el umbral). Pistas débiles, no pruebas.", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


# ====================================================================================
#  INFORME
# ====================================================================================
def escribir_csv(p, candidatos):
    with open(p, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["n", "fila", "columna", "alto_px", "ancho_px", "tamaño_px", "tamaño_mm", "area_px",
                    "puntuacion_media", "pico", "z_densidad", "z_textura", "z_capas", "z_crujido", "que_es",
                    "superficie", "vecinas_lado_a", "vecinas_lado_b", "directo", "inverso", "saturado",
                    "alargamiento", "vecinos_250px", "dist_borde_px"])
        for c in candidatos:
            w.writerow([c["n"], c["fila"], c["col"], c["alto"], c["ancho"], c["tam"],
                        f"{c['tam'] * TAM_PIXEL_UM / 1000:.2f}".replace(".", ","), c["area"],
                        *[f"{c[k]:.3f}".replace(".", ",") for k in ("media", "pico", "densidad", "textura", "capas", "crujido")],
                        c["que_es"], *[f"{c[k]:.2f}".replace(".", ",") for k in ("sup", "vec_a", "vec_b", "fwd", "rev", "saturado", "elong")],
                        c["vecinos"], c["dist_borde"]])


def escribir_informe(p, res, png_mapa, png_cand, csvp):
    N, H, W = res["forma"]
    a = res["args"]
    px_mm = TAM_PIXEL_UM / 1000
    area_cm2 = res["cobertura"] * H * W * (px_mm ** 2) / 100
    L = []
    L.append("MCSerDeLuz - INFORME DE INDICIOS DE TINTA (SIN IA)")
    L.append("=" * 72)
    L.append(f"Fecha:             {datetime.datetime.now():%Y-%m-%d %H:%M}")
    L.append(f"Programa:          buscar_tinta_papiro.py v{VERSION}")
    L.append(f"Segmento:          {res['segmento']}")
    L.append(f"Archivo:           {res['ruta']}  ({mb(res['tam'])})")
    L.append(f"Volumen leído:     {res['interno']}  ({res['tipo']})")
    L.append(f"Tamaño:            {N} capas x {H} filas x {W} columnas  "
             f"({H * px_mm:.1f} x {W * px_mm:.1f} mm a {TAM_PIXEL_UM} µm/px)")
    if res["f"] > 1:
        L.append(f"Resolución:        reducida 1/{res['f']} para no agotar la memoria (coordenadas en px originales)")
    if res.get("trozos"):
        tp, tt = res["trozos"]
        L.append(f"Trozos del zarr:   {tp} de {tt} presentes" + ("" if tp >= tt else
                 " (los que faltan no traen papiro y se tratan como vacío)"))
    L.append(f"Capas:             delante {res['delante']}  |  detrás {res['detras']}  |  vista {res['centro']}")
    L.append(f"Cobertura:         {res['cobertura'] * 100:.1f} % del rectángulo es papiro (≈ {area_cm2:.1f} cm²); "
             f"{res['interior'] * 100:.1f} % queda lejos de bordes y agujeros")
    L.append(f"Pesos:             " + ", ".join(f"{k} {v:.2f}" for k, v in res["pesos"].items()))
    L.append(f"Umbral:            puntuación > {res['umbral']:.2f} (percentil {a.percentil})")
    r = res["rechazos"]
    L.append(f"Manchas:           {res['n_manchas']} sobre el umbral; descartadas: {r['pequeñas']} pequeñas, "
             f"{r['grandes']} grandes, {r['alargadas']} alargadas/huecas, {r['borde/agujero']} en borde o agujero")
    L.append(f"Candidatos:        {len(res['candidatos'])} manchas compactas de {a.tam_min}-{a.tam_max} px "
             f"({a.tam_min * px_mm:.2f}-{a.tam_max * px_mm:.2f} mm)")
    L.append(f"Tiempo:            {res.get('t_total', 0):.0f} s (lectura {res['t_lect']:.0f} s)")
    L.append("")
    L.append("MEJORES CANDIDATOS (fila y columna en píxeles del segmento, como en el cuaderno de Colab)")
    L.append("-" * 72)
    top = res["candidatos"][: a.max_candidatos]
    if not top:
        L.append("Ninguna mancha cumple los criterios. No hay indicios con estos métodos.")
    else:
        L.append(f"{'n':>3} {'fila':>6} {'col':>6} {'alto x ancho':>13} {'mm':>5} {'punt.':>6} {'pico':>5} "
                 f"{'dens':>5} {'text':>5} {'capas':>5} {'cruj':>5}  qué es")
        for c in top:
            L.append(f"{c['n']:>3} {c['fila']:>6} {c['col']:>6} {str(c['alto']) + ' x ' + str(c['ancho']):>13} "
                     f"{c['tam'] * px_mm:>5.2f} {c['media']:>6.2f} {c['pico']:>5.2f} {c['densidad']:>5.2f} "
                     f"{c['textura']:>5.2f} {c['capas']:>5.2f} {c['crujido']:>5.2f}  {c['que_es']}")
        L.append("")
        L.append("Columnas: punt. = puntuación media de la mancha; pico = máxima; dens, text, capas y cruj =")
        L.append("puntuación z media de cada mapa dentro de la mancha (1 = una desviación por encima del fondo).")
        L.append("Un candidato es más interesante si destaca en VARIOS mapas a la vez y si hay otros cerca")
        L.append("alineados como una línea de texto. Uno solo y aislado casi siempre es fibra, grieta o ruido.")
        L.append("")
        L.append("CONTROLES CONTRA FALSOS POSITIVOS (de first-letters-survey, M. Bulloni, MIT)")
        L.append("-" * 72)
        L.append(f"{'n':>3} {'superf.':>7} {'vec.' + str(res['lado_a'][:1]):>9} {'vec.' + str(res['lado_b'][-1:]):>9} "
                 f"{'directo':>7} {'inverso':>7} {'satur.':>6} {'alarg.':>6} {'cerca':>5} {'borde':>5}")
        for c in top:
            L.append(f"{c['n']:>3} {c['sup']:>+7.1f} {c['vec_a']:>+9.1f} {c['vec_b']:>+9.1f} {c['fwd']:>+7.1f} "
                     f"{c['rev']:>+7.1f} {c['saturado']:>6.2f} {c['elong']:>6.1f} {c['vecinos']:>5} {c['dist_borde']:>5}")
        L.append(f"superf./vec. = contraste de la mancha frente a su anillo en las capas {res['delante']} y en las")
        L.append(f"capas vecinas {res['lado_a']} y {res['lado_b']} (si sigue en ambos lados, es un objeto 3D, no tinta).")
        L.append(f"directo/inverso = capas delante menos detrás {res['detras']} frente a delante menos {res['inverso']}")
        L.append("(orden de profundidad invertido: si sale igual, no es algo pegado a la superficie).")
        L.append("satur. = fracción de píxeles muy brillantes; alarg. = alargamiento; cerca = candidatos a < 250 px;")
        L.append("borde = distancia mínima (px) al borde o a un agujero de la malla.")
        L.append("")
        L.append("Qué es: " + "; ".join(f"{v[0]} {sum(c['tipo'] == k for c in res['candidatos'])}" for k, v in TIPOS.items()))
    L.append("")
    L.append("QUÉ MIDE CADA MAPA")
    L.append("-" * 72)
    L.append("1. Densidad: capas delanteras comparadas con su fondo suavizado (~1,3 mm). + = más denso.")
    L.append("2. Textura: fibras desordenadas (poca coherencia de orientación) y variación local alta.")
    L.append(f"3. Capas: capas {res['delante']} menos {res['detras']}; algo pegado solo a la superficie.")
    L.append("4. Crujido: energía de alta frecuencia; la tinta a veces deja una textura granulada.")
    L.append("")
    L.append("AVISO IMPORTANTE")
    L.append("-" * 72)
    L.append("La tinta de Herculano es de carbono y su densidad casi no se distingue de la del papiro")
    L.append("carbonizado. Por eso estos métodos clásicos solo dan PISTAS DÉBILES: fibras cruzadas, grietas,")
    L.append("huecos, restos de capas vecinas o ruido del escáner producen las mismas señales. Ninguno de")
    L.append("estos candidatos es una prueba de escritura. Para confirmarlo hacen falta formas de letra")
    L.append("repetidas y alineadas, que se vean también con el modelo de tinta y en las capas vecinas.")
    L.append("")
    L.append("ARCHIVOS")
    L.append("-" * 72)
    L.append(f"Mapa:        {png_mapa}")
    if png_cand:
        L.append(f"Candidatos:  {png_cand}")
    L.append(f"Tabla CSV:   {csvp}")
    with open(p, "w", encoding="utf-8-sig", newline="\r\n" if os.name == "nt" else "\n") as fh:
        fh.write("\n".join(L) + "\n")


# ====================================================================================
#  VENTANA DE SELECCIÓN (tkinter)
# ====================================================================================
def elegir_con_ventana(encontrados, cache=""):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    eleccion = {"rutas": [], "barrido": None, "recortes": False}
    raiz = tk.Tk()
    raiz.title("MCSerDeLuz - Buscar tinta en el papiro (sin IA)")
    raiz.geometry("900x530")
    tk.Label(raiz, text="Elige uno o varios segmentos y pulsa «Analizar».", font=("Segoe UI", 13, "bold")).pack(pady=(12, 2))
    tk.Label(raiz, text="He buscado en el Escritorio, Descargas y Documentos" + os.sep + "Papiro. "
                        "El zip no se descomprime: solo se leen las capas necesarias.",
             font=("Segoe UI", 10)).pack(pady=(0, 8))
    marco = tk.Frame(raiz); marco.pack(fill="both", expand=True, padx=12)
    lista = tk.Listbox(marco, selectmode="extended", font=("Consolas", 10))
    barra = ttk.Scrollbar(marco, orient="vertical", command=lista.yview)
    lista.configure(yscrollcommand=barra.set)
    lista.pack(side="left", fill="both", expand=True); barra.pack(side="right", fill="y")
    rutas = list(encontrados)

    def refrescar():
        lista.delete(0, "end")
        for p in rutas:
            lista.insert("end", f"{id_segmento(p):<16} {mb(tam_en_disco(p)):>12}   {p}")
        if rutas:
            lista.selection_set(0)

    refrescar()
    if not rutas:
        lista.insert("end", "(no he encontrado segmentos; usa los botones de abajo para elegir uno)")

    def anadir(p):
        if p:
            p = Path(p)
            if p not in rutas:
                rutas.append(p)
            refrescar()
            lista.selection_clear(0, "end"); lista.selection_set(rutas.index(p))

    def elegir_zip():
        anadir(filedialog.askopenfilename(title="Elige el zip del segmento",
                                          filetypes=[("Zip de segmento", "*.zip"), ("Todos", "*.*")]))

    def elegir_carpeta():
        anadir(filedialog.askdirectory(title="Elige la carpeta del segmento (la que contiene surface-volumes)"))

    def analizar_sel():
        sel = [rutas[i] for i in lista.curselection() if i < len(rutas)]
        if not sel:
            messagebox.showinfo("Nada elegido", "Selecciona al menos un segmento de la lista.")
            return
        eleccion["rutas"] = sel
        eleccion["recortes"] = bool(var_rec.get())
        raiz.destroy()

    def barrido_sel():
        r = messagebox.askyesnocancel(
            "Barrido PHerc 1447 (segmentos pequeños)",
            "El barrido recorre los segmentos oficiales de PHerc 1447 de 180 MB o menos (capas 10-21).\n\n"
            "Los que ya tienes en el ordenador se leen directamente. Los demás se DESCARGAN del bucket\n"
            "público del Vesuvius Challenge: unos 100 MB por segmento (en total cerca de 1 GB), a\n"
            f"{cache or carpeta_cache(argparse.Namespace(cache=''))}\n"
            "Si se corta, al repetir continúa donde iba.\n\n"
            "¿Descargar los que falten?\n   Sí = descargar   No = solo los que ya tengo   Cancelar = volver")
        if r is None:
            return
        eleccion["barrido"] = "descargar" if r else "local"
        eleccion["recortes"] = bool(var_rec.get())
        raiz.destroy()

    lista.bind("<Double-Button-1>", lambda e: analizar_sel())
    raiz.bind("<Return>", lambda e: analizar_sel())
    var_rec = tk.BooleanVar(value=False)
    tk.Checkbutton(raiz, text="Exportar recortes de cada candidato (PNG con capa 15, mapa, escala y coordenadas)",
                   variable=var_rec, font=("Segoe UI", 10)).pack(pady=(8, 0))
    botones = tk.Frame(raiz); botones.pack(pady=10)
    tk.Button(botones, text="Analizar", width=16, font=("Segoe UI", 11, "bold"), bg="#d7f0d7",
              command=analizar_sel).pack(side="left", padx=6)
    tk.Button(botones, text="Elegir otro zip...", width=18, command=elegir_zip).pack(side="left", padx=6)
    tk.Button(botones, text="Elegir carpeta...", width=18, command=elegir_carpeta).pack(side="left", padx=6)
    tk.Button(botones, text="Barrido PHerc 1447 (pequeños)...", width=28, bg="#dde8ff",
              command=barrido_sel).pack(side="left", padx=6)
    tk.Button(botones, text="Salir", width=10, command=raiz.destroy).pack(side="left", padx=6)
    tk.Label(raiz, text="Aviso: la tinta de carbono casi no cambia la densidad; el resultado son pistas débiles, no pruebas.",
             fg="#8a4b00", font=("Segoe UI", 9)).pack(pady=(0, 8))
    tk.Label(raiz, text="Barrido: descarga unos 100 MB por segmento que no tengas (cerca de 1 GB en total).",
             fg="#1f3f8a", font=("Segoe UI", 9)).pack(pady=(0, 8))
    raiz.mainloop()
    return eleccion


def elegir_en_consola(encontrados):
    if not encontrados:
        print("No he encontrado segmentos. Escribe la ruta de un zip o carpeta (o pulsa Intro para salir):")
        r = input("> ").strip().strip('"')
        return [Path(r)] if r else []
    print("Segmentos encontrados:")
    for i, p in enumerate(encontrados, 1):
        print(f"  {i}. {id_segmento(p)}  {mb(tam_en_disco(p))}  {p}")
    print("Escribe el número (o varios separados por comas, o 'todos'), o pulsa Intro para salir:")
    r = input("> ").strip().lower()
    if not r:
        return []
    if r in ("todos", "t", "all"):
        return list(encontrados)
    sel = []
    for t in r.split(","):
        t = t.strip()
        if t.isdigit() and 1 <= int(t) <= len(encontrados):
            sel.append(encontrados[int(t) - 1])
    return sel


# ====================================================================================
#  PRINCIPAL
# ====================================================================================
def _lista_enteros(t):
    return [int(x) for x in re.split(r"[,\s;]+", t.strip()) if x]


def main():
    ap = argparse.ArgumentParser(prog="buscar_tinta_papiro.py", add_help=False,
                                 description="MCSerDeLuz - busca indicios de tinta en segmentos del papiro, sin IA.")
    ap.add_argument("rutas", nargs="*", help="zip o carpeta del segmento (si no pones nada, los busca él solo)")
    ap.add_argument("--sin-ventana", "--sinventana", "--headless", dest="sin_ventana", action="store_true",
                    help="no abre ventanas: solo informe de texto y PNG")
    ap.add_argument("--todos", action="store_true", help="analiza todos los segmentos que encuentre")
    ap.add_argument("--delante", type=_lista_enteros, default=CAPAS_DELANTE, help="capas delanteras, p. ej. 14,15,16")
    ap.add_argument("--detras", type=_lista_enteros, default=CAPAS_DETRAS, help="capas de detrás, p. ej. 17,18,19,20")
    ap.add_argument("--tam-min", type=int, default=TAM_TRAZO_MIN, help="tamaño mínimo de trazo en px (30)")
    ap.add_argument("--tam-max", type=int, default=TAM_TRAZO_MAX, help="tamaño máximo de trazo en px (80)")
    ap.add_argument("--percentil", type=float, default=PERCENTIL_UMBRAL, help="percentil del umbral (98.5)")
    ap.add_argument("--max-candidatos", type=int, default=MAX_CANDIDATOS, help="candidatos en el informe (15)")
    ap.add_argument("--sin-crujido", action="store_true", help="no calcula el mapa de crujido")
    ap.add_argument("--reduccion", type=int, default=0, help="reducir resolución 1, 2, 4... (0 = automático)")
    ap.add_argument("--salida", default="", help="carpeta de resultados (por defecto, junto al programa)")
    ap.add_argument("--dpi", type=int, default=110, help="resolución de los PNG")
    ap.add_argument("--exportar-recortes", action="store_true",
                    help="guarda un PNG recortado por candidato (capa 15 + mapa, con escala y coordenadas)")
    ap.add_argument("--barrido", action="store_true",
                    help="barrido de los segmentos pequeños de PHerc 1447 (descarga ~100 MB por segmento que falte)")
    ap.add_argument("--sin-descargas", action="store_true", help="en el barrido, usar solo lo que ya hay en el ordenador")
    ap.add_argument("--limite-mb", type=float, default=180, help="tamaño máximo de segmento del barrido (180 MB)")
    ap.add_argument("--min-papiro", type=float, default=5, help="omitir segmentos con menos papiro (5 %%)")
    ap.add_argument("--z-umbral", type=float, default=4.0, help="umbral z del barrido (4)")
    ap.add_argument("--rehacer", action="store_true", help="repetir segmentos ya analizados en el barrido")
    ap.add_argument("--cache", default="", help="carpeta de descargas del barrido")
    ap.add_argument("--ayuda", "-h", "--help", action="help", help="muestra esta ayuda")
    args = ap.parse_args()
    args.sin_ventana = args.sin_ventana or SIN_VENTANA

    print("MCSerDeLuz - Buscar tinta en el papiro (sin IA) - v" + VERSION)
    print(f"Python {sys.version.split()[0]} | numpy {np.__version__} | matplotlib {matplotlib.__version__} | "
          f"numcodecs {'sí' if numcodecs else 'NO'} | tifffile {'sí' if tifffile else 'NO'} | scipy {'sí' if ndi else 'no (más lento)'}")
    if numcodecs is None:
        print("Aviso: falta 'numcodecs' (viene con zarr). Sin ella no puedo leer zarr comprimidos.\n"
              "       Instálala con:  py -m pip install zarr")

    modo_barrido = "descargar" if args.barrido and not args.sin_descargas else ("local" if args.barrido else None)
    encontrados = None
    if args.rutas:
        rutas = [Path(r.strip('"')) for r in args.rutas]
        malas = [r for r in rutas if not r.exists()]
        if malas:
            _aviso_grave("No encuentro el archivo", "No existe:\n" + "\n".join(map(str, malas)))
            return 1
    else:
        print("Buscando segmentos en:", ", ".join(str(c) for c in carpetas_busqueda()), flush=True)
        encontrados = buscar_segmentos()
        print(f"Encontrados: {len(encontrados)}")
        if args.sin_ventana or modo_barrido:
            rutas = [] if modo_barrido else encontrados
            for p in rutas:
                print("  -", p)
        else:
            try:
                el = elegir_con_ventana(encontrados, str(carpeta_cache(args)))
                rutas, modo_barrido = el["rutas"], el["barrido"]
                args.exportar_recortes = args.exportar_recortes or el["recortes"]
            except Exception as e:
                print("No puedo abrir la ventana de selección (" + str(e) + "); sigo en la consola.")
                rutas = elegir_en_consola(encontrados)
        if not rutas and not modo_barrido:
            print("No hay nada que analizar.")
            return 0

    if modo_barrido:
        args.sin_descargas = modo_barrido == "local"
        if encontrados is None:
            encontrados = list(rutas)
        PROG.iniciar("Barrido PHerc 1447", ventana=not args.sin_ventana)
        try:
            carpeta, filas, fig = barrido(args, encontrados)
        finally:
            PROG.cerrar()
        print("\n" + "=" * 70 + "\nRESUMEN DEL BARRIDO\n" + "=" * 70)
        for r in filas:
            print(f"{r['seg']}: {len(r['candidatos'])} candidatos  ({r.get('estado', '')})  " +
                  ", ".join(f"{TIPOS[t][0]} {n}" for t, n in (r.get('por_tipo') or {}).items() if n))
        print(f"\nResultados en: {carpeta}")
        print("Recuerda: la tinta de carbono casi no cambia la densidad. Son pistas débiles, no pruebas.")
        if not args.sin_ventana:
            try:
                import tkinter as tk
                from tkinter import messagebox
                raiz = tk.Tk(); raiz.withdraw()
                msg = "\n".join(f"{r['seg']}: {len(r['candidatos'])} candidatos" for r in filas)
                abrir = messagebox.askyesno("MCSerDeLuz - barrido terminado",
                                            msg + f"\n\nResultados en:\n{carpeta}\n\n¿Abro la carpeta?")
                raiz.destroy()
                if abrir:
                    abrir_carpeta(carpeta)
            except Exception:
                pass
            if fig is not None:
                plt.show()
                plt.close("all")
        return 0

    resultados, errores = [], []
    PROG.iniciar("Analizando " + (f"{len(rutas)} segmentos" if len(rutas) > 1 else id_segmento(rutas[0])),
                 ventana=not args.sin_ventana)
    for i_r, r in enumerate(rutas):
        PROG.tramo(i_r / len(rutas), (i_r + 1) / len(rutas))
        try:
            resultados.append(analizar(r, args))
        except MemoryError:
            errores.append((r, "Sin memoria suficiente. Prueba con  --reduccion 2  o cierra otros programas."))
        except Exception as e:
            errores.append((r, f"{type(e).__name__}: {e}"))
        plt.close("all") if args.sin_ventana else None
    PROG.tramo(0, 1); PROG.poner(1.0, "terminado"); PROG.cerrar()

    print("\n" + "=" * 70 + "\nRESUMEN\n" + "=" * 70)
    for res in resultados:
        top = res["candidatos"][:3]
        txt = "; ".join(f"#{c['n']} fila {c['fila']} col {c['col']} ({c['tam']} px, {c['media']:.2f})" for c in top)
        print(f"{res['segmento']}: {len(res['candidatos'])} candidatos. {txt or 'ninguno'}")
        print(f"   informe: {res['txt']}")
    for r, e in errores:
        print(f"ERROR en {r}:\n   {e}")
    print("\nRecuerda: la tinta de carbono casi no cambia la densidad. Son pistas débiles, no pruebas.")
    if errores and not args.sin_ventana:
        _aviso_grave("Algún segmento no se pudo analizar", "\n\n".join(f"{r}\n{e}" for r, e in errores))

    if resultados and not args.sin_ventana:
        try:
            from tkinter import messagebox
            import tkinter as tk
            carpeta = resultados[0]["salida"]
            msg = "\n".join(f"{r['segmento']}: {len(r['candidatos'])} candidatos" for r in resultados)
            msg += f"\n\nInforme y mapas guardados en:\n{carpeta}\n\nAhora se abren los mapas; ciérralos para terminar.\n" \
                   "Recuerda: son pistas débiles, no pruebas."
            raiz = tk.Tk(); raiz.withdraw()
            abrir = messagebox.askyesno("MCSerDeLuz - análisis terminado", msg + "\n\n¿Abro la carpeta de resultados?")
            raiz.destroy()
            if abrir:
                abrir_carpeta(carpeta)
        except Exception:
            pass
        plt.show()
        plt.close("all")
    return 1 if errores and not resultados else 0


def _pausa_exe():
    """En el .exe la consola se cierra sola al acabar: esperamos a que el usuario lo lea."""
    if getattr(sys, "frozen", False) and not SIN_VENTANA:
        try:
            input("\nPulsa Intro para cerrar esta ventana...")
        except Exception:
            pass


if __name__ == "__main__":
    import atexit
    atexit.register(_pausa_exe)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _aviso_grave("Error inesperado", f"{type(e).__name__}: {e}\n\nCopia el texto de la consola y envíamelo.")
        sys.exit(1)
