# Образцы PDF

| Файл | Что это |
|---|---|
| `sample-3.pdf` | три страницы подряд: 10-мм пистолет (лёгкое), Гатлинг (тяжёлое), Криолятор (энерго) |
| `sample-3.png` | те же три страницы одним листом для быстрого просмотра |
| `10mm-pistol.pdf`, `gatling-gun.pdf`, `cryolator.pdf` | те же страницы по отдельности |
| `combat-rifle.pdf` | страница 18, собранная из Companion JSON — для сравнения с Publisher-оригиналом |
| `revolver-44.pdf` | «Револьвер калибра .44» без картинки (карточка из `data/weapons/cards/`) |

Во всех образцах картинка оружия — заглушка `assets/pdf/weapons/combat-rifle.png`
(кроме револьвера, где картинки нет). Описания — английские `flavour` из
компаньона. Шрифт — Carlito, метрический клон Calibri.

Пересобрать:

```bash
python3 tools/weapon2pdf.py data/weapons/cards/10mm-pistol.json \
    --out docs/render/samples/10mm-pistol.pdf
```
