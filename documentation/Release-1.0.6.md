# DONNY BOY CZ 1.0.6 – Donny místo delfína

- Donny Boy se svislýma očima nahrazuje delfína při emulaci, příjmu a čtení signálů i ve sdílených výsledkových a varovných obrázcích NFC, RFID, Sub-GHz, iButton a infraportu.
- Devět nových portrétů pasu rozlišuje tři nálady a tři úrovně. Donnyho mají také obě animace zvýšení úrovně, úvodní průvodce, Bluetooth, U2F, DFU, reset PINu a odpojení USB.
- Aktualizátor zobrazuje přesný nápis NAHRAVAM vedle Donnyho kapuce; průběh a stavové hlášky zůstávají čitelné.
- Výchozí SD kolekci tvoří pouze 12 scén DONNY BOY / DARK SIGNAL včetně čtyř automobilových scén, celkem 320 snímků. Je přímo v aktualizačním balíčku a nevyžaduje ruční kopírování ani přepínání motivu.
- Ze zdrojů a nového SD balíčku je odstraněno 38 původních složek animací. Před přípravou SD prostředků se čistí generovaný výstup, aby se staré animace nevracely při inkrementálním sestavení.
- Staré systémové prostředky aktualizátor odstraňuje podle dosavadního instalačního manifestu. Ručně kopírované soubory mimo manifest se hromadně nemažou a nový výchozí manifest je nevybírá.
- Vestavěný DONNY BOY DARK SIGNAL funguje bez SD i při chybě načtení. Donnyho mají také blokující a záložní animace; uložená nálada, zkušenosti a úroveň zůstávají zachované.
- Nahrazené jsou i samostatné kopie obrázků přibalených aplikací HID, T5577, testu Sub-GHz a ukázky obrázků. Soubory cizích FAP aplikací mohou mít vlastní grafiku.
- Web a README mají přehled změn, aktuální galerii dvanácti GIFů a nové náhledy emulace, příjmu a nálad. Kontrola distribučního balíčku odmítá původní animace navíc.
- Základ zůstává Unleashed dev 53818b18 z 16. listopadu 2026, API 88.27. Tato verze nepřidává nový upstream ani nové rádiové protokoly; zachovává funkce z DONNY BOY CZ 1.0.5.

## Instalace a ověření

Pro běžnou aktualizaci použij `flipper-z-f7-update-1.0.6.tgz` z [vydání 1.0.6](https://github.com/luciferbelzebob3-afk/DONNYBOYCZ/releases/tag/v1.0.6). Nech dokončit instalaci SD prostředků; samotné DFU SD animace nedoplní. Soubory mimo starý instalační manifest se hromadně nemažou.

Před publikací jsou povinné úspěšná kompilace, ověření verze a zdroje, kontrola 12 animací a 320 bitmap v aktualizačním balíčku a SHA-256 distribučních souborů. Skutečný zdroj a běh jsou v `sestaveni.json`, výsledky kontroly animací v `animace-overeni.json` a součty v `SHA256SUMS.txt`. **Fyzický test verze 1.0.6 zatím neproběhl.**
