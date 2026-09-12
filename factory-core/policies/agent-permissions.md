# Política de permisos dels agents

## Finalitat

Aquesta política defineix capacitats lògiques per rol. És agnòstica de proveïdor i no és una configuració tècnica de permisos.

## Matriu de permisos

| Acció | Planner | Developer | Reviewer |
|---|---:|---:|---:|
| Llegir requisits, estàndards i context del canvi | Permès | Permès | Permès |
| Interpretar requisits i identificar supòsits | Permès | Permès en implementar | Permès en revisar |
| Produir o modificar un pla d'implementació | Permès | Només proposar | Només recomanar |
| Modificar codi d'aplicació, proves o documentació | No permès | Permès dins l'abast aprovat | No permès |
| Executar validacions locals deterministes | No permès | Permès | Permès per verificar |
| Preparar material de canvi i Pull Request | No permès | Permès | No permès |
| Revisar arquitectura, proves, seguretat i documentació | No permès | Només autocomprovació | Permès |
| Fer merge d'un canvi | No permès | No permès | No permès |
| Desplegar a qualsevol entorn | No permès | No permès | No permès |
| Llegir, modificar o crear secrets | No permès | No permès | No permès |
| Accedir a credencials administratives | No permès | No permès | No permès |
| Administrar Proxmox o altra infraestructura | No permès | No permès | No permès |
| Atorgar permisos o canviar l'enforcement de polítiques | No permès | No permès | No permès |

## Interpretació

«Permès» significa lògicament permès només dins la tasca aprovada i amb la mínima autoritat necessària. No atorga accés remot, credencials, drets de merge ni autoritat de desplegament. A G1, l'executor restringit fusiona després de l'aprovació humana i els controls obligatoris. A G2, el Reviewer només emet un informe i una política determinista versionada pot autoritzar el merge de risc baix; l'executor mecànic continua separat de tots els agents. Cap rol d'agent obté permís de merge o de promoció a producció.
