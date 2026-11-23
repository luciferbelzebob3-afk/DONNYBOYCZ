# DONNY BOY místo delfína

Grafika používá původní pixelovou kapuci DONNY BOY se svislýma očima.
Emulace a vysílání mají ruční vysílač, příjem opačný směr šipky.
Úspěch, uložení, smazání a varování mají vlastní symboly.

- NFC, LF RFID, Sub-GHz, iButton, infraport a sdílené dialogy.
- Devět portrétů pasu: tři nálady × tři úrovně. Náladu odlišují oči
  a ústa, úroveň počet značek na mikině.
- Obě animace zvýšení úrovně, úvodní průvodce, Bluetooth, U2F,
  DFU, reset PINu a odpojení USB.
- Plocha používá výchozí kolekci dvanácti scén `DB_*`. Starých 38 složek
  animací je ze zdrojů odstraněných a do SD balíčku se nezahrnují.
  Blokující stavy a vestavěné záložní animace mají kapuci s mrkáním a pohybem.
- Soukromé kopie obrázků v přibalených aplikacích HID, T5577,
  testu Sub-GHz a ukázce obrázků jsou upravené také.

![Náhled emulace, příjmu, nálad a průvodce](images/donny-mascot-preview.png)

## Zdroje a kontrola

`scripts/donny_mascot_assets.py` vytváří nativní jednobitové PNG pomocí
Pillow a existujícího kreslicího základu ze `scripts/donny_theme_assets.py`.
Spuštění z kořene repozitáře:

```sh
python scripts/donny_mascot_assets.py
```

Částečně upravované obrázky čte ze zdrojového commitu `4443f37e0`, aby
opakované spuštění nepoškodilo původní text. Tento commit musí být dostupný
v místní historii. Skript nespouští sestavení ani GitHub Actions.
Seznam 93 generovaných bitmap je v `documentation/DonnyMascotAssets.json`.
Dalších 320 snímků výchozí kolekce `DB_*` a dvě bitmapy vestavěné
animace DARK SIGNAL jsou samostatné původní zdroje DONNY BOY.

Zůstávají názvy sdílených ikon a SDK symbolů, rozměry a časování
ponechaných animací. Služba `dolphin` dál spravuje původní zkušenosti
a náladu; uložený postup ani logika úrovní se nemění.

Ověřeny byly jednobitový formát, rozměry proti předchozím souborům,
existence snímků odkazovaných metadaty a náhled hlavních obrazovek.
Firmware nebyl sestaven ani otestován na fyzickém Flipperu.

Změny se projeví až po budoucím sestavení a instalaci firmwaru včetně
odpovídajících SD prostředků a přibalených FAP aplikací. Samostatné cizí
FAP soubory a vlastní animace již uložené na SD mohou mít vlastní grafiku;
jejich binární obsah tato úprava zdrojů nemění.

## Aktualizace a výchozí prostředky

Aktualizátor zobrazuje nad průběhem nápis `NAHRAVAM` vedle Donnyho kapuce.
Po instalaci SD prostředků je výchozí manifest složený pouze z našich
dvanácti scén; ruční kopírování ani přepínání motivu není potřeba.
Bez SD karty zůstává vestavěný DONNY BOY DARK SIGNAL.

Existující aktualizátor před rozbalením nových prostředků maže soubory
evidované starým `/ext/Manifest` a odstraňuje prázdné systémové složky.
Původní evidované animace se tak odstraní a nový balíček je nevrací.
Při přípravě SD prostředků se navíc čistí generovaný výstup animací,
aby staré soubory nezůstaly ani po inkrementálním sestavení.
Kontrola hotového balíčku odmítne jinou než výchozí kolekci `DB_*`.

Soubory mimo starý instalační manifest se hromadně nemažou. Pokud manifest
chybí nebo byly animace kopírované ručně, jejich staré soubory mohou na SD
zůstat; nový výchozí manifest je ale nevybírá. Uživatelské záznamy NFC,
RFID, Sub-GHz, IR a iButton tato změna neupravuje.
