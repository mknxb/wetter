# Build für iOS 12

`test/index.src.html` ist die Quelle (modernes JS/CSS). `test/index.html` wird daraus erzeugt und läuft auch auf Safari 12.

    cd tools && npm install && npm run build    # nur bauen
    npm run check                               # bauen + Kompatibilitätsprüfung

Nur die `.src.html` bearbeiten, danach neu bauen und beide Dateien committen.
Den Radar-Entpacker für alte Browser (`assets/fflate-inflate.js`) erzeugt: `npx esbuild fflate-entry.js --bundle --minify --target=safari12 --format=iife --outfile=../assets/fflate-inflate.js`
