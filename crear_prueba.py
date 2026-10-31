"""Crea segmentos sintéticos (zarr v2, blosc) en un zip para las pruebas del .exe.
   python crear_prueba.py            -> MCSerDeLuz-prueba-20990101000000.zip (3 manchas, 640x640)
   python crear_prueba.py --muchos   -> MCSerDeLuz-prueba-20990101000001.zip (64 manchas, 1920x1920)"""
import sys, json, zipfile, numpy as np, numcodecs
muchos = "--muchos" in sys.argv
N, C = 31, 128
H = W = 1920 if muchos else 640
rng = np.random.default_rng(1)
vol = (rng.normal(120, 12, (N, H, W))).clip(1, 255).astype(np.uint8)
vol[:, :40] = 0; vol[:, 300:340, 300:340] = 0           # borde y agujero
if muchos:
    sitios = [(140 + 220 * i + (j % 2) * 30, 140 + 220 * j) for i in range(8) for j in range(8)]
    seg = "20990101000001"
    for y, x in sitios:                                  # 64 manchas densas en la superficie
        vol[14:17, y:y + 34, x:x + 30] = 200
else:
    seg = "20990101000000"
    for y, x in [(200, 200), (230, 260), (210, 320)]:    # tres manchas densas en la superficie
        vol[14:17, y:y + 40, x:x + 35] = 200
codec = numcodecs.Blosc(cname="lz4", clevel=5, shuffle=1)
pre = f"{seg}-prueba/surface-volumes/prueba.zarr/0/"
with zipfile.ZipFile(f"MCSerDeLuz-prueba-{seg}.zip", "w") as z:
    z.writestr(pre + ".zarray", json.dumps({"zarr_format": 2, "shape": [N, H, W], "chunks": [N, C, C], "dtype": "|u1",
               "compressor": codec.get_config(), "fill_value": 0, "order": "C", "filters": None,
               "dimension_separator": "."}))
    for iy in range(H // C):
        for ix in range(W // C):
            z.writestr(pre + f"0.{iy}.{ix}", codec.encode(np.ascontiguousarray(vol[:, iy*C:(iy+1)*C, ix*C:(ix+1)*C])))
print("ok", seg)
