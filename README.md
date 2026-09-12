# Software Factory POC

Projecció pública d'una prova de concepte de Software Factory agèntica. El
repositori mostra una selecció sanejada de contractes, polítiques, codi de
governança, escenaris i plantilles reproduïbles.

Forgejo és l'única font de veritat. Aquest repositori és una projecció passiva
i retardada: no accepta canvis operatius, no replica l'historial privat i no
conté credencials, evidència d'execució, configuració interna d'infraestructura
ni workflows actius de GitHub Actions.

La projecció es construeix amb una llista blanca versionada i s'atura si detecta
un tipus de fitxer no admès, una ruta prohibida o un patró sensible. Per tant,
una actualització de Forgejo pot trigar a aparèixer aquí o quedar bloquejada fins
que es resolgui una troballa.

## Contingut principal

- `factory-core/`: estàndards, polítiques i components portables seleccionats.
- `templates/fastapi-service/`: plantilla de servei FastAPI.
- `benchmarks/incidents-api/`: aplicació de referència.
- `benchmarks/scenarios/`: definició dels escenaris de benchmark.

El mecanisme de selecció es pot auditar a
`factory-core/policies/public-repository-projection-v1.json` i
`factory-core/tools/public_repository_projection.py`.
