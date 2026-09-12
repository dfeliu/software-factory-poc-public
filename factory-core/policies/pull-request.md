# Política de Pull Request

## Unitat de canvi

- Cada objectiu acceptat rep un `change_id` immutable i, com a màxim, una PR.
- El Builder treballa primer en un workspace o branca efímers. Els reintents,
  correccions i revisions actualitzen la mateixa branca i la mateixa PR.
- La PR s'obre quan el canvi ja supera els checks locals mínims. Pot començar
  com a draft i només deixa de ser-ho quan el Reviewer i la CI tenen evidència.
- Un nou *head commit* invalida la revisió i l'elegibilitat anteriors.
- Obrir una segona PR per al mateix `change_id` és un error de contracte.

## Governança

- G0: revisió, aprovació i merge humans.
- G1: aprovació humana vigent i merge mecànic restringit.
- G2: un Reviewer independent aporta `pass`, `needs_human` o `fail`; una
  política determinista separada decideix l'elegibilitat de risc baix.
- Cap agent aprova ni fa merge. La identitat restringida de l'executor no pot
  modificar codi ni ampliar la política.
- Els canvis sensibles, ambigus, fora de límits o de governança escalen a humà.
- La PR conserva objectiu, criteris d'acceptació, abast, validació, límits i
  referències d'evidència, però mai secrets ni prompts complets.

El contracte executable és a `factory-core/policies/enforcement/` i el model de
decisió és a `factory-core/policies/governance-levels.md`.
