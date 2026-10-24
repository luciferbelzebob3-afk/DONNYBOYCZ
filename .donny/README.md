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
Nové neznámé texty používají Gemini a secret `GEMINI_API_KEY`. Volitelná
repository variable `GEMINI_TRANSLATION_MODEL` dovoluje `gemini-2.5-flash`
(výchozí) nebo `gemini-2.5-flash-lite`, oba s dokumentovaným bezplatným tarifem.
OpenAI ani jiná placená záloha se nevolá.

Vytvoř klíč na https://aistudio.google.com/api-keys v projektu **bez zapnuté
fakturace** a ulož ho v Settings → Secrets and variables → Actions jako
`GEMINI_API_KEY`. Samotný kód nedokáže zjistit fakturační tarif Google projektu;
klíč z placeného projektu by Google mohl účtovat. Automatizace fakturaci
nezapíná, nepropojuje účet a při kvótě nepřechází na jiný model ani poskytovatele.
Bezplatný tarif podléhá kvótám a podmínkám zpracování dat Googlu.

Workflow `check-gemini-key.yml` ověří skutečným minimálním požadavkem stejného
klienta strukturovaných odpovědí. Pokud klíč chybí, výslovně uvede, že živé
ověření nebylo provedeno; není třeba posílat klíč do chatu.

Úspěšné dávky se ukládají do `gemini-cache.json` podle modelu, vstupu i schématu.
Při HTTP 429 se kandidát zachová v integrační větvi spolu s `deferred.json`.
Další plánované běhy respektují čas obnovení (obvykle 15 minut, denní kvóta
24 hodin), potom pokračují bez nového čísla verze a bez opakování hotových dávek.
Dočasné síťové chyby a HTTP 5xx mají omezené opakování, poté odklad.
Neúplná, blokovaná nebo schématu neodpovídající odpověď nesmí povolit vydání.
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
python -m unittest discover -s .github/tests -p 'test_*.py' -v
```

Diagnostické artefakty patří vždy ke konkrétnímu ID a pokusu workflow. Síťové
chyby se nezaměňují za stav „žádná aktualizace“. Koncept vydání lze doplnit,
zveřejněné vydání zůstává při chybě webu dostupné.

