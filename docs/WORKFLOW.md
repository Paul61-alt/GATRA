# WORKFLOW — RADAR (2 devs)

Doc volontairement court. Niveau hackathon : assez de discipline pour ne plus se marcher dessus, pas plus.

## Pourquoi ce doc existe

On s'est retrouvés avec **3 branches qui réécrivent le même fichier** (`screens-overview.jsx`) en parallèle, jamais fusionnées. Résultat : la fusion finale devient un cauchemar de conflits, et c'est là qu'on casse des trucs sans le voir. Ce doc supprime cette situation.

---

## 1. Règle d'or

`main` est **toujours déployable** (Vercel auto-deploy depuis `main`).
**Rien ne tombe sur `main` sans une Pull Request.** Jamais de commit direct sur `main`.

## 2. Qui touche quoi (ownership)

| Zone | Owner | Chemin |
|------|-------|--------|
| Backend (moteur, pipeline, evals, models) | **Paul** | `radar/backend/**` |
| Frontend (écrans, UI) | **Cofounder** | `radar/frontend-prototype/**` |
| Contrat front/back (l'interface entre les deux) | **À deux** | `radar/frontend-prototype/FRONTEND_CONTRACT.md` |

Effet : vos fichiers ne se chevauchent quasi plus → quasi zéro conflit.

> **⚠️ Cette règle vaut pour la suite, pas rétroactivement.**
> Les features frontend déjà commencées de part et d'autre (y compris celles de Paul) **ne sont pas perdues** : on les intègre d'abord (voir Annexe), puis on applique le split à partir de là. Si une tâche oblige à toucher la zone de l'autre, on se le dit **avant** et on coordonne — on ne fork pas en silence.

## 3. Cycle d'une tâche (4 étapes)

```bash
# 1. Toujours partir de main à jour
git switch main && git pull

# 2. Une branche courte par tâche
git switch -c fix/ma-tache

# 3. Commit souvent. JAMAIS changer de branche avec un arbre sale
#    (commit ou `git stash` d'abord)
git add -A && git commit -m "..."

# 4. Avant la PR : se resynchroniser sur main, résoudre les conflits
#    SUR SA BRANCHE (pas sur main)
git switch main && git pull
git switch fix/ma-tache && git rebase main
# ... résoudre conflits éventuels, puis push
git push -u origin fix/ma-tache
```

Puis : ouvrir la PR sur GitHub → merge → **supprimer la branche** (`git branch -d fix/ma-tache` + delete remote).

## 4. Cadence

**Fusionner sur `main` tous les jours.** Petites fusions = petits problèmes. Une grosse fusion à la fin = cauchemar. C'est la règle la plus importante de tout le doc.

---

## Annexe — Nettoyage du graveyard actuel

État au moment d'écrire ce doc : 13 branches, jamais fusionnées. Ordre de nettoyage recommandé (à exécuter manuellement, en suivant le cycle §3) :

1. **`origin/backend`** → déjà dans `main` (0 commit d'avance). **Supprimer.**
2. **Petites `fix/*` backend-only** (9–44 lignes, aucun conflit) — mergeables en premier, sans risque :
   `fix/pricing-tiers`, `fix/similarity-threat`, `fix/eval-e2e-synthesize`, `fix/dedup-verify`, `fix/improve-speed-pipeline`.
3. **`fix/backend_setup`** → WIP (1 commit, +583 lignes). Clarifier avant de merger.
4. **Les 3 grosses branches frontend** qui se chevauchent sur `screens-overview.jsx` / `screens-map.jsx` —
   `front-math` (cofounder), `feat/linkedin-posts`, `fix/timeline-log-scale-toggle` :
   choisir **UNE base**, rebaser les deux autres dessus une par une, tester entre chaque. À traiter quand la branche chatbot du cofounder est pushée, pour tout intégrer en un seul passage propre.

## Note — branche "chatbot"

Au moment d'écrire ce doc, la branche chatbot du cofounder **n'est pas sur `origin`**. `front-math` (sa seule branche poussée) est un redesign frontend, pas un chatbot. → Lui demander de **push sa branche chatbot** avant toute intégration.
