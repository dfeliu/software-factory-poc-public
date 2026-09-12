# Estàndard d'arquitectura

## Finalitat

Aquest estàndard defineix les qualitats arquitectòniques esperades dels projectes produïts per la factory. S'aplica independentment del runtime o proveïdor seleccionat durant la POC.

## Requisits mínims

- Mantenir explícites i cohesionades les responsabilitats i els límits dels mòduls.
- Declarar les dependències de l'aplicació i externalitzar la configuració respecte del codi font.
- Aïllar les integracions específiques de proveïdor darrere de límits clars quan s'introdueixin.
- Fer visibles a la documentació del projecte els modes de fallada i les dependències operatives.
- Preferir dissenys simples que es puguin provar, revisar, reproduir i traslladar entre proveïdors.

## Fora d'abast

Aquest estàndard no escull un framework, una base de dades, una topologia de desplegament, un proveïdor, una estructura de repositori ni la implementació del Golden Path.
