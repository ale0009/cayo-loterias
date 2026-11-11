# zxing-wasm 3.1.6 (incluido sin cambios)

Lector de códigos de barras [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp) compilado a WebAssembly por [zxing-wasm](https://github.com/Sec-ant/zxing-wasm). Licencias: MIT (zxing-wasm, ver LICENSE) y Apache 2.0 (zxing-cpp).

Se incluye en el repositorio para que la herramienta no dependa de un CDN. `js/lector-foto.js` le indica que cargue `zxing_reader.wasm` desde esta carpeta.

En el piloto leyó los 3 billetes sintéticos (cerca, lejos y girado) y 5 de las 20 fotos reales de loterías. El port viejo `vendor/zxing.min.js` no leyó ninguno.
