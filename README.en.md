# ¿Cayó? ("Did it hit?")

**Check whether your Colombian lottery ticket or Baloto ticket won.** Type the 20 digits printed under the barcode, scan it with your camera, or fill in a form. The tool compares it with the official results and the full prize plan: jackpot, fixed "secos" prizes, and every partial match.

[Español](README.md) · [How it was made (Spanish)](proceso/)

## Features
- **Three ways to check:** the 20-digit code (lottery, draw, number, series and fraction in one), live camera scan, or a manual form (lottery or Baloto ball picker).
- **Clear verdict:** net prize per fraction, prize category, claim deadline with a countdown, and where to claim.
- **Wallet:** tickets are saved in your browser. Tickets for future draws are checked automatically when results arrive. Export and import supported.
- **When did my number hit?:** search a 4-digit number across every jackpot and seco of the last year.
- **11 games supported:** Baloto, Revancha, and the Medellín, Boyacá, Valle, Huila, Santander, Cauca, Tolima, Quindío, Risaralda and Extra de Colombia lotteries, including each plan's special categories.
- **Not yet:** Bogotá and Meta use anti-bot protection (never bypassed); Cundinamarca, Manizales and Cruz Roja only publish scanned records or images.

## Self-sustaining by design
No server, no database, no API keys, no AI. A Python collector (standard library only) runs nightly on GitHub Actions. It fetches new draws from the official sources and commits them as JSON in `datos/`. The page is static (GitHub Pages) and does all the math in the browser.

## Local use
```bash
python3 -m http.server 8000
node --test
python3 recolectores/actualizar.py
```

## Origin
A real pilot: 80 ticket photos received over Telegram turned out to be 20 unique tickets. Three held small prizes nobody had noticed, because none of them matched the jackpot.

## Disclaimer
Independent tool, not affiliated with any lottery or with Coljuegos. Always verify with the official source before claiming. Prizes expire one year after the draw (Law 1393 of 2010, art. 12).

## Credits
[Mario Puerta «ale0009»](https://github.com/ale0009) × [David Rincón «Kuronoma»](https://www.linkedin.com/in/davidalexanderrinconcorredorkuronoma/) · Barcode reader: [ZXing](https://github.com/zxing-js/library) (MIT). Code license: MIT.
