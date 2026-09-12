# Estàndard d'observabilitat

## Finalitat

Aquest estàndard defineix l'evidència de diagnòstic que un servei generat hauria de posar a disposició a mesura que evoluciona la POC.

## Requisits mínims

- Generar logs estructurats i contextuals adequats per diagnosticar comportaments i errors.
- No incloure secrets, credencials ni dades personals innecessàries als logs.
- Exposar un senyal de salut adequat a les dependències declarades del servei.
- Conservar prou context per relacionar un error informat amb el canvi o l'execució pertinent.
- Documentar les mancances de diagnòstic i els supòsits coneguts.
- Tractar qualsevol dashboard com una projecció derivada i regenerable: no pot
  reescriure evidència, autoritzar accions ni convertir camps absents en èxit.
- Quan s'agreguin diverses fonts, publicar la frescor i l'estat de cada
  productor separadament de l'hora de generació del projector.
- Aplicar una allow-list explícita a cada adaptador; no propagar metadata
  arbitrària, logs, prompts, secrets ni query strings d'URL.

## Fora d'abast

Aquest estàndard no selecciona un backend de logs, un proveïdor de monitoratge, un quadre de comandament, una política d'alertes, un període de retenció ni una implementació d'infraestructura.
