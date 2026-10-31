#!/usr/bin/env bash
# MCSerDeLuz - Buscar tinta en el papiro (sin IA) - lanzador para Linux
# Uso:  ./buscar_tinta_papiro.sh            (ventana para elegir segmento)
#       ./buscar_tinta_papiro.sh --barrido  (y cualquier otra opcion de --ayuda)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/buscar_tinta_papiro.py"
if [ ! -f "$SCRIPT" ]; then
  echo "No encuentro buscar_tinta_papiro.py junto a este archivo."; exit 1
fi
PY=""
for c in "$DIR/.venv-buscar-tinta/bin/python" "$HOME/.venv-buscar-tinta/bin/python" python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  cat <<'TXT'
======================================================================
 No encuentro Python 3. Instalalo (Debian/Ubuntu):
     sudo apt install python3 python3-venv python3-tk
 y despues:
     python3 -m venv ~/.venv-buscar-tinta
     ~/.venv-buscar-tinta/bin/pip install numpy zarr tifffile matplotlib scipy
 Mas detalles en MCSerDeLuz-instrucciones-buscar-tinta.txt
======================================================================
TXT
  exit 1
fi
"$PY" "$SCRIPT" "$@"
code=$?
# si se abrio con doble clic (terminal propia), esperar antes de cerrar
if [ -t 0 ] && [ -z "$BUSCAR_TINTA_SIN_PAUSA" ]; then
  case " $* " in *" --sin-ventana "*) ;; *) read -r -p "Pulsa Intro para cerrar... " _ ;; esac
fi
exit $code
