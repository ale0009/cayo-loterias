# ¿Cayó?

**Revisa si tu billete de lotería o tu tiquete de Baloto ganó.** Escribe los 20 números que vienen bajo el código de barras, escanéalo con la cámara o llena el formulario. La herramienta lo compara con los resultados oficiales y con el plan de premios completo: mayor, secos y todas las aproximaciones.

[English](README.en.md) · [Cómo se hizo](proceso/)

## Qué hace
- **Tres formas de consulta:** código de 20 dígitos (lotería, sorteo, número, serie y fracción en uno), cámara en vivo, o formulario a mano (lotería o Baloto con bolillero).
- **Veredicto claro:** ¡Cayó! o No cayó, el valor neto por fracción, la categoría, la fecha límite para cobrar con un medidor de días y dónde cobrarlo.
- **Billetera:** guarda tus boletos en el navegador. Los de sorteos futuros se revisan solos cuando llegan los resultados. Se puede exportar e importar.
- **¿Cuándo cayó mi número?:** busca un número de 4 cifras en todos los mayores y secos del último año.
- **Soporta 11 juegos:** Baloto, Revancha y las loterías de Medellín, Boyacá, Valle, Huila, Santander, Cauca, Tolima, Quindío, Risaralda y el Extra de Colombia. Incluye las categorías propias de cada plan: anterior y posterior al mayor, mayor invertido, cifras en otro orden, cifras del centro y «gana fijo».
- **Fuera, por ahora:** Bogotá y Meta tienen protección anti-robots, que no se evade. Cundinamarca, Manizales y Cruz Roja solo publican actas o imágenes escaneadas: leerlas exigiría OCR, y un error de lectura daría un «No cayó» falso.

## Cómo se sostiene sola
No hay servidor, base de datos, claves ni IA. Un recolector en Python (solo biblioteca estándar) corre cada noche en GitHub Actions, trae los sorteos nuevos de las fuentes oficiales y los guarda como JSON en `datos/`. La página es estática (GitHub Pages) y hace todo el cálculo en el navegador.

```
recolectores/actualizar.py   → datos/<juego>.json                    (cada noche)
recolectores/loterias/*.py   → un módulo por lotería (se registran solos)
datos/planes.json            → valores netos de cada plan de premios
js/motor.js                  → reglas de premios (funciones puras, con pruebas)
```

## Uso local
```bash
python3 -m http.server 8000         # abre http://localhost:8000
node --test                         # pruebas del motor y las gráficas
python3 recolectores/actualizar.py  # actualizar los datos a mano
```

## Agregar una lotería
1. Crea `recolectores/loterias/<id>.py` con `NOMBRE`, `FUENTE`, `lista()` → `[(sorteo, 'AAAA-MM-DD')]` y `sorteo(s, fecha)` → `{mayor: {numero, serie}, secos: [{numero, serie, valor}]}`. Se registra solo.
2. Agrega su plan en `datos/planes.json`: netos por billete, código de barras si se conoce y, si los tiene, sus premios propios en `neto_billete_extra`.
3. Agrega un caso real en `test/motor.test.js`.

Reglas: solo fuentes oficiales, una consulta por sorteo y nunca evadir CAPTCHAs ni protecciones anti-robots.

## De qué trabajo sale
De un piloto real: 80 fotos de boletos que llegaron por Telegram resultaron ser 20 boletos distintos. Tres tenían premios pequeños que nadie había visto, porque ninguno coincidía con el mayor. Toda la investigación está en [proceso/](proceso/).

## Aviso
Herramienta independiente: no está afiliada a ninguna lotería ni a Coljuegos. Verifica siempre en la fuente oficial antes de cobrar. Los premios vencen un año después del sorteo (Ley 1393 de 2010, art. 12). Juega con responsabilidad.

## Créditos
[Mario Puerta «ale0009»](https://github.com/ale0009) × [David Rincón «Kuronoma»](https://www.linkedin.com/in/davidalexanderrinconcorredorkuronoma/)

Lector de códigos de barras: [ZXing](https://github.com/zxing-js/library) (MIT), incluido en `vendor/`. Licencia del código: MIT. Los resultados son información pública de cada lotería.
