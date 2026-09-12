# Estàndard de proves

## Finalitat

Aquest estàndard defineix l'evidència mínima esperada abans de proposar un canvi generat per la factory per a revisió.

## Requisits mínims

- Les proves han de ser deterministes i executables des de la documentació del projecte.
- Cal provar el comportament observable, incloent-hi errors esperats i condicions de límit quan sigui rellevant.
- En corregir un defecte reproduïble, cal afegir o modificar una prova de regressió.
- Després d'un canvi, cal executar la suite de proves pertinent i informar-ne del resultat.
- Les dades de prova han de romandre aïllades de credencials, dades de producció i serveis externs no gestionats.

## Fora d'abast

Aquest estàndard no defineix un framework de proves, un llindar de cobertura, un entorn de proves, un workflow de CI ni un servei de proves específic d'un proveïdor.
