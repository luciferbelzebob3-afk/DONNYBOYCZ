# DONNY BOY — DARK SIGNAL

Výchozí monochromatický motiv pro DONNYBOYCZ, větev `dev`.
Základ implementace: `58ccd4e6f90f245d72e58a81fff090879522ce86`.

## Co je součástí firmware

- Horizontální hlavní menu s velkou ikonou výběru, bočními ikonami a českými názvy.
- Vlastní symboly Sub-GHz, NFC, RFID, IR, GPIO, klíče, USB a nastavení.
  Neznámé aplikace si ponechávají vlastní původní ikonu.
- Vestavěná animace postavy v kapuci u terminálu; krátké bliknutí antény přibližně
  jednou za osm sekund. Není potřeba kopírovat asset pack ani menu `.fal` na SD.
- Zámek s monogramem DB a skutečným časem RTC. PIN a trojí stisk Back fungují
  podle původního zabezpečení; na obrazovce se zobrazuje odpovídající pokyn.
- Tmavé nabídky nastavení, inverzní výběr, vlastní malé symboly, tmavé dialogy
  a jednoduchý stavový řádek se skutečnými stavovými ikonami.

Grafika je přizpůsobená skutečnému rastru 128 × 64, plocha ponechává horních
13 řádků stavovému řádku. Velký koncepční obrázek není screenshot firmware:
na fyzickém LCD jsou detaily postavy a písma přirozeně jednodušší.
Oranžová v prezentaci není barva displeje.

## Výchozí vzhled a stávající nastavení

Při prvním načtení nastavení verze 18 se vizuální volby převedou na verzi 19:
vestavěný DARK SIGNAL a baterie s procenty. Zkratky, automatické zamykání,
hodiny a USB volby se zachovají. Verze 17 a 14 se nadále načítají původními
migračními cestami. Následný ruční výběr jiného nainstalovaného menu stylu
zůstává uložený; DARK SIGNAL je v nabídce stylů vestavěná výchozí položka.
Samotný formát `DesktopSettings` ani ABI `MenuStyle` se nemění.

Před instalací zálohujte data zařízení a zejména interní `.desktop.settings`.
Při návratu na starší firmware, který nezná verzi nastavení 19, obnovte také
zálohu původního nastavení plochy. Jinak starší firmware použije vlastní výchozí
nastavení plochy. PIN je spravován původním mechanismem, tento motiv ho nemění.

## Sestavení

Použijte kompletní checkout `DONNYBOYCZ/dev` s inicializovanými submoduly.
Na Windows:

```powershell
.\fbt.cmd -j8 COMPACT=1 DEBUG=0 DIST_SUFFIX=donny-dark-signal UPDATE_VERSION_STRING=1.0.0-dark-signal updater_package
```

Na Linux/macOS nahraďte `.\fbt.cmd` za `./fbt`.
Výsledek je `dist/f7-C/flipper-z-f7-update-donny-dark-signal.tgz`.
Sestavení samo nezapisuje na zařízení. Na Windows udržujte krátkou cestu
checkoutu, protože ARM nástroje mohou selhat na příliš dlouhých cestách.

## Instalace hotového balíku

V qFlipper vyberte instalaci firmware ze souboru a zvolte hotový aktualizační
`.tgz` balík pro Flipper Zero f7. Neinstalujte samostatný zdrojový ZIP jako
firmware. Standardní aktualizace nainstaluje firmware i jeho přibalené aplikace
a SD prostředky; samotný motiv plochy a vestavěné menu jsou dostupné bez SD.

## Ověření při vytvoření (2026-10-28)

- Kompletní sestavení `updater_package` s release volbami prošlo.
- Nativní test skutečného kódu DARK SIGNAL a stejných u8g2 fontů ověřil
  8 256 pozic menu, šipky, obousměrné přetáčení, prázdný model, dlouhý text
  a kreslení zámku s PIN i bez PIN. Ochranné bajty framebufferu zůstaly zachované.
- Samostatně kompilovaný skutečný `desktop_settings.c` ověřil přechod 18 → 19,
  zachování zkratek/auto-lock/USB/hodin, přechod z verze 17 a výchozí hodnoty.
  Pozdější vlastní styl se neobnovuje na výchozí a načítání verze 19 zbytečně nezapisuje.
- PNG snímky a metadata prošly skutečným interním Dolphin compilerem firmware.

Fyzické zařízení nebylo v této relaci připojeno ani flashováno. Na něm zbývá
ověřit čitelnost a polaritu LCD, levou ruku, tlačítka a návraty, funkci PIN,
stavové ikony, první start s SD i bez SD a probuzení ze zámku. Nativní test
rendereru není plná emulace operačního systému Flipperu.

## Úpravy grafiky

Zdrojové snímky a metadata jsou v
`assets/dolphin/internal/DB_DarkSignal_128x51/`. Neměňte rozměry bez aktualizace
metadat. Seznam interních animací je v `assets/dolphin/internal/manifest.txt`;
výběr výchozí animace řeší `animation_manager.c`. Výstrahy, level-up a dummy mode
zůstávají řízené původním stavovým automatem.

Kreslení ikon, menu a monogramu najdete v
`applications/services/gui/modules/dark_signal.c`. Motiv nevyžaduje nový font
ani změnu uživatelských překladů. Původní licence firmware platí nadále;
nové C části a pixelové podklady se poskytují pod stejnou licencí GPL-3.0.
