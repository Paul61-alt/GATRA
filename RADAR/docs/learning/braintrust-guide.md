# Braintrust — Guide pour RADAR

> **Public :** non-tech / PM technique. Pas de jargon inutile. Exemples tirés de RADAR.

---

## Niveau 1 — C'est quoi, et pourquoi ça existe ?

### Le problème que Braintrust résout

Tu construis RADAR. RADAR appelle Linkup et retourne un profil de compétiteurs.
La question naturelle : **est-ce que le résultat est bon ?**

Sans outil, tu fais ça à la main :
- tu lances RADAR sur `linear.app`
- tu regardes le JSON sorti
- tu juges "ça a l'air bien" ou "c'est nul"
- tu changes un mot dans le prompt
- tu relances
- tu essaies de te souvenir si c'était mieux avant

C'est ingérable dès que tu as 5 domaines de test et 3 versions de prompt.

**Braintrust automatise ça.**

---

### Ce que Braintrust fait concrètement

Braintrust est une plateforme d'**évaluation de systèmes IA**. Elle te permet de :

1. **Lancer ton code sur un dataset** (tes 8 domaines de test)
2. **Scorer automatiquement les outputs** (via un juge LLM ou du code)
3. **Stocker le résultat comme snapshot immuable** (un "experiment")
4. **Comparer deux versions** côte à côte dans un dashboard

Le cycle ressemble à ça :

```
Tu changes un prompt dans understand.py
         ↓
Tu lances : bt eval evals/eval_understand.py
         ↓
Braintrust exécute ton code sur les 8 domaines
         ↓
Chaque output est scoré (0.0 → 1.0)
         ↓
Tu vois : "understand-v2 score = 0.83 vs understand-v1 = 0.71"
         ↓
Tu sais si ton changement était une amélioration
```

---

### L'analogie simple

Imagine que tu as un **stagiaire** qui teste chaque version de ton produit
sur 8 entreprises fictives et te rend une note sur 10.

Braintrust = ce stagiaire, mais automatisé et qui se souvient de tout.

---

### Pourquoi c'est pertinent pour RADAR spécifiquement

RADAR a 3 phases distinctes :

| Phase | Ce qu'elle fait | Risque d'échec |
|-------|-----------------|----------------|
| UNDERSTAND | Profil entreprise | Données manquantes, hallucinations |
| DISCOVER | Liste compétiteurs | Compétiteurs non pertinents, doublons |
| ENRICH | Pricing + signaux | Sources inexistantes, données vides |

Chaque phase peut déraper indépendamment. Sans eval, tu ne sais pas laquelle.
Avec Braintrust, tu as un score par phase, par domaine testé.

---

## Niveau 2 — Comment ça marche sous le capot ?

### Les 3 composants d'un Eval

Chaque eval Braintrust a exactement 3 parties :

**1. Data** — tes cas de test
```python
data = [
    {"input": "linear.app"},
    {"input": "notion.so"},
    {"input": "mistral.ai"},
]
```
C'est juste une liste d'inputs. Optionnellement tu peux ajouter `expected`
si tu connais la réponse attendue (pas notre cas : on n'a pas de vérité terrain).

**2. Task** — ton code à évaluer
```python
async def task(domain: str) -> dict:
    linkup = LinkupClient()
    profile = await understand_run(domain, linkup)
    return profile.model_dump(mode="json")
```
Braintrust appelle cette fonction pour chaque item du dataset.
Il récupère l'output.

**3. Scores** — comment juger l'output
```python
def score_completeness(input, expected, output):
    return ClosedQA()(
        input=f"Domaine: {input}",
        output=str(output),
        criteria="Le profil contient name, summary, hq_city, hq_country..."
    )
```
Un scorer prend `(input, expected, output)` et retourne un score entre 0.0 et 1.0.

---

### LLM-as-judge — le concept clé

Pour RADAR, on n'a pas de "bonne réponse" absolue.
On ne peut pas écrire `assert output["name"] == "Linear"`.

La solution : utiliser un LLM (GPT-4 ou Claude) comme juge.

On lui donne :
- l'input (le domaine)
- l'output (ce que RADAR a sorti)
- un critère (ce qu'on attend)

Il répond oui/non → score 1.0 ou 0.0.

C'est ce que `ClosedQA` fait dans autoevals.
C'est imparfait (le juge peut se tromper) mais suffisant pour détecter les régressions.

---

### Les "Experiments" — snapshots immuables

Chaque fois que tu lances `bt eval`, Braintrust crée un **experiment** :
- nom : `understand-v1`, `understand-v2`...
- scores par domaine : `linear.app → 0.9`, `cal.com → 0.4`
- timestamp + metadata (model, phase, etc.)

Ces snapshots ne changent jamais. Tu peux toujours revenir comparer
`understand-v1` vs `understand-v3` 6 mois plus tard.

---

### Le Tracing — observer l'intérieur

En plus des evals, Braintrust peut tracer l'exécution de ton code.
Dans RADAR, on a ajouté `@traced` sur `claude_client.py` :

```python
@traced
def extract_json(self, system, user, max_tokens):
    ...
```

Ça crée des "spans" dans le dashboard — tu vois :
- combien de temps chaque appel a pris
- l'input exact envoyé au LLM
- l'output exact reçu
- les tokens utilisés (et le coût)

Utile pour débugger : "pourquoi ce domaine a un score bas ?" → tu vois
exactement ce qui a été envoyé et reçu.

---

## Niveau 3 — La perspective "production"

### Scoring quantitatif vs qualitatif

Notre setup actuel utilise LLM-as-judge → scores subjectifs.
Problème : le juge lui-même peut varier d'un run à l'autre.

À maturité, tu voudras ajouter des scorers **déterministes** (code pur) :
- `score_has_hq` : `1.0` si `hq_city` non null, `0.0` sinon
- `score_competitor_count` : `n / 15` (score proportionnel au nombre trouvé)
- `score_no_duplicate_domains` : détecte les doublons dans DISCOVER

Ces scorers sont 100% reproductibles. Combine-les avec LLM-as-judge pour
avoir une vue complète.

---

### Online Scoring — évaluer en production

Ce qu'on a setup = **offline eval** : tu lances manuellement avant de déployer.

Braintrust supporte aussi **online scoring** :
- chaque requête prod est tracée automatiquement
- un scorer LLM évalue l'output async (sans impacter la latency)
- tu vois des métriques en temps réel sur tes vrais utilisateurs

Pour RADAR, ça voudrait dire : chaque analyse lancée depuis l'interface
est automatiquement scorée et apparaît dans le dashboard.

À faire quand tu auras assez de trafic pour que ça ait du sens.

---

### Datasets vivants

Actuellement, les datasets sont hardcodés dans `evals/datasets.py`.

Braintrust a un système de **datasets managés** : tu peux créer un dataset
dans l'UI, y ajouter des cas au fil du temps (depuis les vrais outputs prod
qui étaient mauvais), et tes evals s'exécutent automatiquement dessus.

Workflow idéal :
1. RADAR sort un résultat mauvais sur `pennylane.com`
2. Tu l'ajoutes au dataset Braintrust comme cas de régression
3. Chaque future version de RADAR est testée dessus automatiquement

---

### CI/CD — bloquer les régressions

Quand tu auras une baseline stable, tu peux ajouter dans GitHub Actions :

```yaml
- name: Run evals
  run: bt eval evals/ --no-input --json
  env:
    BRAINTRUST_API_KEY: ${{ secrets.BRAINTRUST_API_KEY }}
```

Si le score moyen chute de plus de 10%, le deploy est bloqué.
C'est le "test de non-régression" pour les systèmes IA.

---

## Résumé pratique

| Concept | Ce que c'est | Dans RADAR |
|---------|-------------|-----------|
| **Experiment** | Run d'eval avec snapshot | `understand-v1`, `discover-v2`... |
| **Dataset** | Liste de cas de test | 8 domaines dans `datasets.py` |
| **Task** | Ton code à tester | `run()` de chaque phase |
| **Scorer** | Fonction de notation 0→1 | `score_completeness`, `score_count`... |
| **LLM-as-judge** | GPT/Claude comme évaluateur | `ClosedQA` d'autoevals |
| **Trace** | Log d'un appel LLM | Spans de `@traced` dans claude_client |
| **Online scoring** | Eval sur trafic prod | À faire plus tard |

---

## Workflow quotidien (une fois tout setup)

```
1. Tu changes un prompt dans understand.py / discover.py
2. bt eval evals/eval_understand.py
3. Dashboard Braintrust → compare avec version précédente
4. Score monte → tu gardes. Score baisse → tu reverts.
5. Tu commits avec un experiment_name daté
```

Temps par itération : ~3-5 min (le temps que Linkup réponde).
Valeur : tu sais objectivement si ton changement a amélioré les choses.
