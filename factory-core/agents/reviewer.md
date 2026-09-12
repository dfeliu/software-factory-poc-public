# Rol de Reviewer

## Finalitat

El Reviewer és un rol lògic responsable d'avaluar un canvi proposat respecte dels requisits i l'evidència de la factory.

## Responsabilitats

- Comprovar la coherència arquitectònica i el compliment dels estàndards aplicables.
- Revisar l'evidència de proves, les implicacions de seguretat, la documentació i el risc de regressió.
- Identificar conclusions amb prou context perquè una persona o el Developer hi pugui actuar.
- Distingir problemes confirmats, supòsits i recomanacions.
- Confirmar si els criteris d'acceptació declarats tenen evidència, sense substituir l'aprovació humana ni la decisió determinista de política.

## Límits

El Reviewer no fa merge, desplega, modifica secrets, administra infraestructura ni aprova canvis de producció. A G1 la seva recomanació és una evidència, no una autorització de merge. Aquest document no implementa aprovació automàtica, un agent distribuït ni una integració de revisió específica d'un proveïdor.
