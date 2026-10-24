# Automatická vydání DONNY BOY CZ

Řídicí workflow `.github/workflows/sync-unleashed.yml` sleduje poslední stabilní
GitHub Release projektu DarkFlippers/unleashed-firmware. Kontrola běží každých
pět minut mimo celou hodinu; GitHub může plánovaný běh opozdit. Okamžitý upstream
webhook není připojen. Podporované ruční spuštění: Actions → DONNY BOY CZ –
automatické stabilní vydání → Run workflow. Oprávněný relay může použít
`repository_dispatch` s typem `unleashed-stable-release`.

Navazující fáze jsou příprava → samostatná analýza → samostatný překlad →
samostatný build → publikace → explicitní nasazení a ověření GitHub Pages.
Celý řetězec používá společný zámek, přesná SHA a jednu rezervovanou patch verzi.
Push nebo release vytvořený `GITHUB_TOKEN` nemusí spustit další workflow;
proto jsou návaznosti vyjádřené přes `needs` a `workflow_call`.

## Trvalá evidence

- `pending.json`: upstream release ID, tag, SHA, společný základ a rezervovaná verze.
- `memory.json`: původní celé literály, české překlady a kontext jejich použití.
- `analysis.json`: úplný seznam nových literálů, klasifikace a otisky zdrojů.
- `translation-report.json`: počty nových, znovu použitých a technických řetězců.
- `completed.json`: zapisuje se teprve po publikaci a ověření živého webu.
- `reviewed.json`: ručně posouzené položky podle přesné identity zdroje a kontextu.
- `upstream-notes-cs.json`: ověřené české přehledy změn podle upstream SHA.
- `templates/`: společné šablony aktuálního README a webu; historii nepřepisují.

Integrační větev `automation/stable-release` uchovává nedokončený výsledek.
Při selhání se vydání neoznačí za dokončené. Opakovaný běh navazuje na stejnou
verzi. Po publikaci se opakuje pouze aktualizace webu, bez nového buildu.
Pokud se během přípravy změnila větev dev, publikace se zastaví; existující
kandidát zůstane zachován pro novou integraci a ověření.

## Překlad a klíče

Již zkontrolované texty a překladová paměť nepotřebují model ani API klíč.
Nové neznámé texty používají existující secret `OPENAI_API_KEY` a volitelnou
repository variable `OPENAI_TRANSLATION_MODEL` (výchozí `gpt-4.1-mini`).
Volání API může čerpat kredit poskytovatele; samotný tarif ChatGPT jej neposkytuje.
Bez klíče se běh s neznámými texty zastaví a uloží podklady k ručnímu posouzení.
Nevydá potichu nepřeloženou aktualizaci. Nejasné texty také blokují vydání.

Model dostává pouze nové položky a kontext; nevrací celé upravené soubory.
Před zápisem se kontrolují identita, otisk souboru, celé literály, escape sekvence,
pořadí printf parametrů, ASCII a maximální délka. Funkční merge konflikty,
přejmenování nebo odstranění lokálně upravených souborů vyžadují posouzení;
neřeší se plošným upřednostněním jedné strany.

## Distribuce a web

Build a tag používají stejný commit a verzi. Povinné jsou firmware DFU, updater
DFU, aktualizační TGZ a metadata. Ověřuje se struktura archivů a SHA-256, včetně
serverových digestů nahraných souborů. Zveřejněné tagy a soubory se nepřepisují.

Jediný v repozitáři doložený vlastní web je
https://luciferbelzebob3-afk.github.io/DONNYBOYCZ/ (zdroj `site/`).
Metadata aktuálního vydání jsou v `site/release.json`. README, jeho odznaky,
odkazy, šablona chyb a index webu se aktualizují společně. Nové fyzické testování
se nepředpokládá na základě výsledku staršího vydání 1.0.1.

## Ověření logiky

```bash
python -m unittest discover -s .github/tests -p test_donny_pipeline.py -v
```

Diagnostické artefakty patří vždy ke konkrétnímu ID a pokusu workflow. Síťové
chyby se nezaměňují za stav „žádná aktualizace“. Koncept vydání lze doplnit,
zveřejněné vydání zůstává při chybě webu dostupné.
