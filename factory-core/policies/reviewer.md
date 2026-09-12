# Política del Reviewer independent

El Reviewer de G2 s'executa en un context separat del Builder. Rep l'objectiu,
el diff, els resultats dels checks i les normes aplicables; no hereta les
conclusions ni el raonament privat del Builder.

L'informe és estructurat i queda vinculat a `change_id`, número d'intent,
`objective_hash` i `head_sha`. El resultat pot ser:

- `pass`: no s'han trobat impediments; és només una entrada a la política;
- `fail`: hi ha defectes corregibles i el Builder pot reintentar sobre la
  mateixa PR mentre quedi pressupost;
- `needs_human`: cal judici semàntic, hi ha ambigüitat o el risc no és
  classificable automàticament.

Un `pass` no substitueix cap check determinista, no amplia paths ni límits i no
és una aprovació SCM. Cada nou *head* exigeix un informe nou. Es conserven les
troballes com codis, severitat, path i referència d'evidència; no s'hi admeten
text lliure, prompts complets ni secrets.
