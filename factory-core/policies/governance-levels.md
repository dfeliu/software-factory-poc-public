# Nivells de governança i elegibilitat de merge

## Finalitat

Aquesta política separa quatre portes: acceptació tècnica del Builder, revisió
independent, elegibilitat de merge i promoció d'entorn. Una PR no equival a una
autorització de producció. Durant la neteja, G0 és l'únic nivell actiu.

## Nivells

| Nivell | Autorització | Executor de merge | Estat |
|---|---|---|---|
| G0 | aprovació humana | persona responsable | actiu |
| G1 | aprovació humana vigent | executor restringit | evidència històrica; retirat operativament |
| G2 | política determinista per a risc baix; humana per a la resta | executor restringit | pausat; repositoris disposables només |
| G3 | política de risc i promoció operacional | executor restringit | diferit |

G2 només es podria aplicar a repositoris disposables, sense dades reals ni
producció, després d'una decisió explícita de reactivació. No converteix cap
agent en aprovador: el Reviewer aporta un senyal i la política versionada
decideix. L'executor només materialitza una decisió elegible.

## Fonts de veritat

- Les polítiques d'enforcement i el manifest d'activació són JSON versionat a
  `factory-core/policies/enforcement/`.
- El hash SHA-256 del fitxer actiu forma part de cada decisió. El commit de
  `factory-core` forma part de l'evidència d'execució.
- Els esdeveniments JSON locals són immutables i reproduïbles.
- PostgreSQL és una projecció append-only per consultar i auditar; mai no pot
  ampliar permisos ni substituir Git com a font normativa.
- Markdown explica el model, però no és executable.

## Contracte futur de G2

Una decisió només és `eligible` quan, per a la mateixa PR i *head commit*:

1. el repositori, la branca base i la identitat Builder estan permesos;
2. el diff queda dins dels paths, tipus de canvi i límits versionats;
3. tots els checks obligatoris són `success`;
4. un Reviewer independent retorna `pass` per l'objectiu i el *head* exactes;
5. la PR és oberta, no és draft, és fusionable i l'estat extern és inequívoc;
6. el pressupost d'intents i temps no s'ha superat;
7. la política activa coincideix exactament amb el seu hash i la decisió no ha
   caducat.

`blocked` torna al bucle Builder–Reviewer sobre la mateixa PR si queda
pressupost. `needs_human` atura el canvi. Qualsevol dada absent, desconeguda,
inconsistent o ambigua és restrictiva i mai es converteix en `eligible`.

## Separació de capacitats

- Builder i Reviewer no tenen credencials de merge.
- El Builder no declara autoritativament el risc ni pot ampliar l'allowlist.
- L'avaluador és pur, determinista, sense xarxa i sense credencials.
- L'executor usa una identitat restringida, torna a consultar Forgejo i
  revalida política, *head*, autor, branca i checks just abans del merge.
- Un canvi a política, activació, workflows, permisos o proteccions sempre és
  `needs_human` i requereix una PR humana de governança.
- La promoció a producció continua prohibida als agents i fora de G2.

## HOTL i parada

La supervisió humana és posterior: s'auditen tots els primers merges automàtics
i després una mostra determinista. Una auditoria adversa, una regressió, una
reversió o una discrepància d'evidència activa una pausa local de repositori o
global. La pausa només restringeix; reactivar requereix una decisió humana i un
canvi operatiu explícit.

## Bootstrap i activació

Una futura reactivació de G2 ha d'entrar primer en `shadow`. Passar a
`enforced` requereix evidència satisfactòria de S6G2 i una PR separada aprovada
humanament. Aquesta aprovació de bootstrap autoritza la política; no aprova
cadascun dels canvis futurs que compleixin el contracte.
