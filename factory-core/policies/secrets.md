# Política de secrets

## Política

- No emmagatzemar secrets, credencials ni tokens administratius a Git.
- No exposar secrets al codi font, la documentació, fixtures de prova, logs, comandes o informes.
- Utilitzar marcadors documentats i valors d'exemple que no puguin autenticar.
- Tractar una exposició sospitosa com un problema bloquejant que requereix intervenció humana.
- Demanar l'accés de mínim privilegi necessari quan una fase posterior introdueixi una integració.
- No desar una credencial de merge o desplegament com a secret d'un motor de
  workflows si un rol que no pot tenir aquesta autoritat pot publicar o
  modificar workflows dins del mateix repositori. Aquesta credencial s'ha
  d'aïllar en un pla d'execució separat.

## Fora d'abast

Aquesta política no escull un gestor de secrets, un format de credencial, un procés de rotació ni un mecanisme d'accés específic d'un proveïdor.
