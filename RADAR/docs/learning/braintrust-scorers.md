# Comment créer de bons critères d'évaluation

> Suite de `braintrust-guide.md`. Focus : design de scorers.
> Public : non-tech / PM technique.

---

## Partie 1 — Comment j'ai choisi les critères actuels

Méthode appliquée pour chaque phase de RADAR :

1. **Regarde le modèle de sortie** (Pydantic `CompanyProfile`, `CompetitorProfile`)
2. **Liste les champs critiques** — sans quoi le résultat est inutile
3. **Imagine 3 "outputs cassés"** plausibles
4. **Pour chaque cassure → un scorer**

### Phase 1 — UNDERSTAND

**Modèle :** `CompanyProfile` avec `name`, `summary`, `hq`, `funding`, `markets`, `positioning`...

**Outputs cassés plausibles :**
| Cassure | Détection |
|---------|-----------|
| Champs vides (Linkup n'a rien trouvé) | Code : compte champs non-null |
| Champs remplis mais faux (hallucination) | LLM judge : "est-ce plausible ?" |
| Pas de markets identifiés | Code : `len(markets) > 0` |

**Scorers retenus :**
- `score_completeness` — LLM judge : profil complet + valeurs plausibles + pas d'hallucination
- `score_markets` — code : ≥1 market

### Phase 2 — DISCOVER

**Modèle :** liste de dicts compétiteurs avec `name`, `website`, `one_liner`...

**Outputs cassés plausibles :**
| Cassure | Détection |
|---------|-----------|
| 2 compétiteurs trouvés au lieu de 15 | Code : `n / 15` avec paliers |
| Compétiteurs hors marché (Spotify pour Linear) | LLM judge : relevance |
| Compétiteurs sans website/description | Code : taux de remplissage |

**Scorers retenus :**
- `score_count` — code : 10+ = 1.0, 5+ = 0.5, sinon 0
- `score_relevance` — LLM judge : vrais compétiteurs même marché
- `score_data_quality` — code : fraction avec website + one_liner

### Phase 3 — ENRICH

**Modèle :** `CompetitorProfile` avec `pricing`, `recent_signals`...

**Outputs cassés plausibles :**
| Cassure | Détection |
|---------|-----------|
| Pas de source pricing | Code : fraction avec `source_url` |
| Signaux vides ou génériques ("growing") | LLM judge : événements spécifiques |

**Scorers retenus :**
- `score_pricing_coverage` — code : fraction avec source URL
- `score_signals_quality` — LLM judge : signaux spécifiques

---

## Partie 2 — Les principes d'un bon scorer

### Principe 1 : un scorer = une dimension

Pas de scorer "global qualité". Un scorer mesure **une chose**.

❌ `score_quality` — vague, impossible à diagnostiquer si baisse
✅ `score_completeness` + `score_relevance` + `score_count` — chacun isolé

**Pourquoi :** quand le score baisse, tu veux savoir **où**. Si tout est dans un seul score, tu sais qu'il y a un problème mais pas lequel.

### Principe 2 : 0.0 → 1.0, pas binaire

❌ `return True / False` → tu vois "ça passe / ça passe pas"
✅ `return 0.0 → 1.0` → tu vois la **progression** (0.4 → 0.6 = mieux)

**Pourquoi :** un binaire reste à 0 jusqu'au jour où tu passes. Tu n'as aucun signal de progrès intermédiaire. Avec un float, chaque petite amélioration se voit.

### Principe 3 : code d'abord, LLM judge ensuite

Si tu peux mesurer en code → fais-le en code.

| Mesurable en code | Nécessite LLM judge |
|-------------------|---------------------|
| Champ rempli ou non | Valeur plausible ou pas |
| Nombre d'items | Compétiteur vraiment dans le marché |
| Présence d'URL source | Description "spécifique" ou "générique" |
| Doublons détectés | Hallucination détectée |

**Pourquoi :** code = déterministe, gratuit, rapide. LLM judge = subjectif, coûte des tokens, lent.

### Principe 4 : critères LLM judge — sois précis

❌ "L'output est bon"
❌ "La réponse est utile"
✅ "Le profil contient name, summary, hq_city, hq_country non-null. Les valeurs sont plausibles pour le domaine donné. Pas de placeholder ni hallucination évidente."

**Pourquoi :** un LLM avec un critère vague invente sa propre rubrique → variance énorme entre runs. Critère précis = score reproductible.

### Principe 5 : score ce qui fait mal en prod

Ne pas scorer ce qui est "joli". Scorer ce qui casse l'usage.

Pour RADAR :
- ✅ "Compétiteurs hors marché" → casse la valeur produit
- ❌ "Style de la description" → impact nul utilisateur

---

## Partie 3 — Méthode pour créer tes propres scorers

### Étape 1 — Liste les modes d'échec

Lance ta pipeline sur 5-10 cas variés. Note les sorties qui te font dire "non, ça c'est nul".

Pour chaque sortie nulle, demande-toi : **pourquoi c'est nul ?**

Exemple sur DISCOVER :
- "Il a sorti Adobe Photoshop comme compétiteur de Figma" → mode d'échec = compétiteurs hors marché
- "Il a sorti 3 compétiteurs au lieu de 15" → mode d'échec = sous-population
- "Il a sorti Figma comme compétiteur de Figma" → mode d'échec = auto-référence

### Étape 2 — Classe : code ou LLM judge ?

Pour chaque mode d'échec, demande : **est-ce détectable par une règle simple ?**

- Auto-référence → code (`competitor.name == target.name`)
- Sous-population → code (`len(competitors)`)
- Hors marché → LLM judge (sémantique)

### Étape 3 — Écris le scorer le plus simple qui marche

Pas d'optimisation prématurée. 5 lignes max au début.

```python
def score_no_self_reference(input, expected, output):
    target = input.lower()
    names = [c.get("name", "").lower() for c in output]
    return 0.0 if any(target in n for n in names) else 1.0
```

### Étape 4 — Calibre sur 3 cas

Avant de tout lancer :
- 1 cas où tu sais que l'output est **bon** → scorer doit retourner ~1.0
- 1 cas où tu sais que l'output est **moyen** → scorer doit retourner ~0.5
- 1 cas où tu sais que l'output est **mauvais** → scorer doit retourner ~0.0

Si ton scorer ne distingue pas les 3, il est cassé. Réécris-le.

### Étape 5 — Itère

Tu vas découvrir d'autres modes d'échec en regardant les runs. Ajoute-les comme nouveaux scorers. Ne touche pas aux anciens (tu casserais la comparabilité avec les experiments passés).

---

## Partie 4 — Anti-patterns à éviter

### ❌ Scorer l'effort, pas le résultat

```python
# Mauvais : score si le code a essayé
def score_attempted_discovery(input, expected, output):
    return 1.0 if output is not None else 0.0
```

Output non-null ≠ output bon. Score le **contenu**, pas l'existence.

### ❌ Scorer trop strict

```python
# Mauvais : exige exactement 15 compétiteurs
def score_count(input, expected, output):
    return 1.0 if len(output) == 15 else 0.0
```

14 compétiteurs c'est très bien. Score progressif :

```python
def score_count(input, expected, output):
    return min(len(output) / 15, 1.0)
```

### ❌ LLM judge avec critère composite

```python
# Mauvais : 4 trucs dans un seul critère
criteria = "Le profil est complet, plausible, bien formaté, et utile."
```

Un seul critère par scorer. Sinon le LLM judge fait une moyenne floue dans sa tête → score peu signifiant.

### ❌ Pas de baseline

Tu lances ton premier eval, score = 0.7. Et alors ? 0.7 c'est bien ? mal ?

**Toujours commencer par une baseline figée** (ex : `understand-baseline`). Toutes les futures versions comparent contre elle.

---

## Partie 5 — Archétypes de scorers réutilisables

Bibliothèque mentale pour t'inspirer :

| Archétype | Question | Exemple RADAR |
|-----------|----------|---------------|
| **Coverage** | Quelle fraction de champs remplie ? | `score_data_quality` |
| **Count** | Combien d'items produits ? | `score_count` |
| **Plausibility** | Le contenu est-il réaliste ? | `score_relevance` (LLM) |
| **Format** | Le schéma est-il respecté ? | Pydantic le fait gratos |
| **Diversity** | Y a-t-il des doublons ? | À ajouter sur DISCOVER |
| **Recency** | Les dates sont-elles fraîches ? | À ajouter sur ENRICH signals |
| **Citation** | Y a-t-il une source ? | `score_pricing_coverage` |
| **Self-reference** | L'output référence-t-il l'input ? | À ajouter sur DISCOVER |

---

## TL;DR

1. Liste les modes d'échec en regardant des outputs réels
2. Code pour ce qui est mesurable, LLM judge pour le sémantique
3. Un scorer = une dimension, score entre 0 et 1
4. Critère LLM = précis, jamais vague
5. Calibre sur 3 cas (bon / moyen / mauvais) avant de lancer
6. Score le résultat, pas l'effort
