"""Crea un segmento sintético pequeño (zarr v2, blosc) en un zip para la prueba del .exe."""
import json, zipfile, numpy as np, numcodecs
N, H, W, C = 31, 640, 640, 128
rng = np.random.default_rng(1)
vol = (rng.normal(120, 12, (N, H, W))).clip(1, 255).astype(np.uint8)
vol[:, :40] = 0; vol[:, 300:340, 300:340] = 0           # borde y agujero
for y, x in [(200, 200), (230, 260), (210, 320)]:        # tres manchas densas en la superficie
    vol[14:17, y:y + 40, x:x + 35] = 200
codec = numcodecs.Blosc(cname="lz4", clevel=5, shuffle=1)
pre = "20990101000000-prueba/surface-volumes/prueba.zarr/0/"
with zipfile.ZipFile("MCSerDeLuz-prueba-20990101000000.zip", "w") as z:
    z.writestr(pre + ".zarray", json.dumps({"zarr_format": 2, "shape": [N, H, W], "chunks": [N, C, C], "dtype": "|u1",
               "compressor": codec.get_config(), "fill_value": 0, "order": "C", "filters": None,
               "dimension_separator": "."}))
    for iy in range(H // C):
        for ix in range(W // C):
            z.writestr(pre + f"0.{iy}.{ix}", codec.encode(np.ascontiguousarray(vol[:, iy*C:(iy+1)*C, ix*C:(ix+1)*C])))
print("ok")
