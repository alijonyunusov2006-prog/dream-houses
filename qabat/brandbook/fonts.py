# Собирает fonts.css для брендбука: Montserrat и Inter (OFL) с латиницей, кириллицей и таджикскими буквами, base64.
# Шрифты берутся из npm (@fontsource), сеть к Google Fonts не нужна.
#   cd <папка> && npm pack @fontsource/montserrat @fontsource/inter && распаковать в fontsource-<имя>-<версия>/
#   python3 fonts.py <папка-с-распакованными-пакетами> > fonts.css
import base64, glob, os, sys
root = sys.argv[1] if len(sys.argv) > 1 else '.'
RANGES = {'latin': 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD',
          'cyrillic': 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116',
          'cyrillic-ext': 'U+0460-052F,U+1C80-1C8A,U+20B4,U+2DE0-2DFF,U+A640-A69F,U+FE2E-FE2F'}
for fam, name in (('Montserrat', 'montserrat'), ('Inter', 'inter')):
    pkg = sorted(glob.glob(os.path.join(root, f'fontsource-{name}-*', 'package')))[-1]
    for w in (400, 500, 600, 700):
        for sub, rng in RANGES.items():
            f = os.path.join(pkg, 'files', f'{name}-{sub}-{w}-normal.woff2')
            b = base64.b64encode(open(f, 'rb').read()).decode()
            print(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;src:url(data:font/woff2;base64,{b}) format('woff2');unicode-range:{rng};}}")
