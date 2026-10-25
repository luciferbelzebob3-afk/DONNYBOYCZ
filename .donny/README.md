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

## Překlad přímo na serveru GitHubu

Analýzu, překlad a české poznámky vytváří otevřený Qwen3-8B Q4_K_M přes
`llama.cpp` spuštěný na CPU stejného GitHub Actions runneru. Není potřeba
Codespace, vlastní zapnutý počítač, účet u AI poskytovatele ani AI API klíč.
OpenAI a Gemini se z překladového řetězce nevolají; žádná placená záloha není.
GitHub token slouží nadále pouze k práci s repozitářem a vydáním.

Model se stáhne až při prvním neznámém textu a zkontroluje se celý SHA-256.
Soubory a licence modelu i přesný commit runtime jsou v `local-model.lock.json`.
Váhy mají přibližně 5 GB a zůstávají ve složce runneru, nikoli v repozitáři,
na počítači uživatele nebo v distribučním balíčku firmwaru. Cache vah a připnutého CPU runtime využívá běžný bezplatný limit GitHub Actions;
limit úložiště nezvyšujeme. Runtime se sestavuje bez optimalizace pro konkrétní
procesor a jeho cache je omezená na standardní Ubuntu 24 x64.
Inference přijímá požadavky pouze přes `127.0.0.1`. Není veřejně vystavená.
Stažení vah a zdrojů runtime stále vyžaduje internet.

Používají se standardní linuxové runnery veřejného repozitáře, nikoli placené
větší/GPU runnery. Provoz podléhá pravidlům, časovým a úložným limitům GitHubu.
Změna repozitáře na soukromý by změnila podmínky bezplatného výpočetního času.

Programové kontroly celých literálů, ASCII, printf parametrů, řídicích sekvencí,
délek a otisků zdrojových souborů zůstávají zachované. Model vrací jen malé
JSON dávky (nejvýše čtyři položky), nesmí přepisovat celé zdrojové soubory.
Známé české diakritické znaky v překladech displeje se deterministicky převedou
na ASCII; poznámky k vydání zůstávají s diakritikou. Technické názvy a klíče
souborových formátů se nepřekládají. Nejasná klasifikace blokuje vydání.

Hotové odpovědi se ukládají do `model-cache.json` podle přesného modelu,
runtime, vstupu i schématu; překladová paměť v `memory.json` se zachovává.
Pokud pozdější dávka selže, už ověřené odpovědi se uloží do integrační větve.
Dočasná nedostupnost runner-local modelu odloží kandidáta přes `deferred.json`;
další plánovaný běh respektuje čas obnovení a nevytváří další verzi.
Chybný SHA-256 modelu, neplatná/neúplná odpověď nebo porušené placeholdery
nesmějí povolit publikaci nepřeloženého nebo neověřeného vydání. Model upravuje jen slovní části. Program sám zachovává původní printf
parametry, C escape sekvence, okolní mezery a interpunkci a přeložené části
sestaví zpět do celého literálu. Rozpočet slovních částí odečítá pevné technické
znaky z povolené délky. Nevalidní překlad dostane nejvýše jeden lokální opravný
požadavek; text se nikdy násilně neořezává a všechny stejné kontroly se provedou
i po opravě. Do cache se ukládá až ověřený celek; ID zdroje ani technické značky
model měnit nemůže.

Workflow `check-local-model.yml` skutečně spustí váhy na CPU a ověří krátké
české překlady, formátovaný text a odlišení UI od logů a serializovaných klíčů.
Výsledek a čas běhu jsou uložené jako diagnostický artefakt. Tato kontrola
není zárukou bezchybného překladu libovolného budoucího textu; nejasné nebo
nevalidní výsledky vyžadují opravu před vydáním. První stažení a sestavení
runtime může trvat několik minut; CPU je pomalejší než velké hostované modely.

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
