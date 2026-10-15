# QA LOG
_Last updated: 2026-10-15 | Version: 2.7.0_

## Threat model — surfaces d'entrée

| Surface | Privilège | Exposition |
|---|---|---|
| API RSQA / Open-Meteo / Gemini | sortant HTTPS | réponses tierces parsées en JSON |
| `remote_server` `:8088` | lecture + écriture sur `arts/`, capture d'écran, navigation | **sans authentification**, lié à `127.0.0.1` |
| Fichiers déposés par Telegram | écrits dans `arts/`, lus par ffmpeg et Gemini | contenu entièrement contrôlé par l'expéditeur |
| `arts/*.json` (cartels en cache) | lus et affichés | écrits par l'app, mais modifiables par qui a un accès shell |
| ffmpeg (sous-process) | mêmes droits que l'app, session dédiée | consomme des médias non fiables |

---

## Security Audit

### Lecture vidéo par pipe ffmpeg — 2026-10-14
- **Threat model:** injection d'arguments par le nom de fichier ; média malformé ; process orphelin ou zombie ; épuisement mémoire du cgroup ; fuite de chemin dans les messages d'erreur.
- **Tests run:**
  - lancement sur `.mp4` valide 480×640 (portrait) et 1280×720 — lecture nominale ;
  - `.mp4` tronqué à 3 000 octets, déposé via `/api/art/upload` ;
  - `.mp4` constitué de 50 Ko d'octets aléatoires ;
  - suppression d'un média **pendant** sa lecture ;
  - inspection des process ffmpeg et des zombies après chaque cycle.
- **Result:** **pass**, après deux correctifs appliqués dans la même session.
- **Findings:**
  - *Injection d'arguments* — **non exploitable** : ffmpeg est lancé en liste d'arguments, jamais via un shell, et l'extension est déduite des octets magiques et non du nom. Les octets aléatoires sont rejetés à l'upload avant d'atteindre le disque.
  - *Fuite de chemin* — **low, corrigé** : stderr de ffmpeg citait le chemin absolu dans le message affiché à l'écran. Remplacé par le seul nom de fichier.
  - *Orphelins* — **pass** : `start_new_session=True` + `killpg` ; aucun ffmpeg résiduel après `on_exit`, suppression de média ou arrêt du service.

### API `remote_server` — 2026-10-14
- **Threat model:** endpoints d'upload et de suppression sans authentification.
- **Result:** **conditional** — acceptable tant que l'écoute reste sur `127.0.0.1`.
- **Findings:** `BUG-003` ci-dessous. Risque accepté pour l'usage actuel (bot Telegram local), à rouvrir avant toute exposition LAN.

---

## Bug Registry

### [BUG-001] — La vidéo n'a jamais été lue, et l'UI affichait un succès
- **Severity:** critical
- **Scenario:** envoyer une vidéo au bot Telegram, ouvrir le mode Musée.
- **Expected:** la vidéo joue en boucle.
- **Actual:** écran noir portant « ▶ `fichier.mp4` — Lecture en boucle ». mpv était lancé puis mourait instantanément ; `play()` renvoyait `True` parce que `Popen` avait réussi, et le placeholder affichait donc l'état de succès sur une panne totale.
- **Root cause:** aucun player externe ne peut rendre sur cette machine — CRT sur connecteur Composite au statut `unknown` (refusé par le code KMS de mpv), pas de serveur X, `/dev/fb0` détenu par SDL 1.2. Confirmé par test direct de mpv, ffplay et cvlc.
- **Status:** fixed in 2.5.1 — décodage par pipe ffmpeg ; l'état est désormais relu à chaque frame via `player.status()`, qui distingue `starting` / `playing` / `error`.

### [BUG-002] — Interblocage à l'arrêt du décodeur, gel du rendu et zombie
- **Severity:** high
- **Scenario:** supprimer ou changer un média pendant la lecture d'une vidéo.
- **Expected:** arrêt immédiat, aucun process résiduel.
- **Actual:** ffmpeg survivait 2 s puis laissait un process `<defunct>`, la boucle de rendu gelant pendant ce temps.
- **Root cause:** `_stop_locked()` attendait la mort de ffmpeg **en tenant le verrou**. Le thread de lecture se bloquait sur ce même verrou, cessait de vider stdout, et ffmpeg restait coincé dans un `write()` sur un pipe plein sans pouvoir traiter son SIGTERM. Le `wait()` expirait, le SIGKILL suivant n'était pas suivi d'un second `wait()` — d'où le zombie.
- **Status:** fixed in 2.5.1 — découpage en `_detach()` (sous verrou) / `_terminate()` (hors verrou), plus un `wait()` après SIGKILL. Latence de suppression mesurée après correctif : **500 ms**, aucun process résiduel, aucun zombie.

### [BUG-003] — API HTTP sans authentification
- **Severity:** medium
- **Scenario:** si `AIRQ_API_HOST` était élargi au LAN, n'importe qui pourrait téléverser, supprimer et capturer l'écran.
- **Expected:** écriture authentifiée.
- **Actual:** aucun contrôle d'accès ; mitigé uniquement par le binding `127.0.0.1`.
- **Status:** open — risque accepté pour l'usage local actuel. **À corriger avant toute exposition réseau.**

### [BUG-004] — `/api/art/select` ne re-scanne pas `arts/`
- **Severity:** low
- **Scenario:** déposer un fichier dans `arts/` hors API, puis `POST /api/art/select` avec ce nom.
- **Expected:** soit la sélection aboutit, soit une erreur explicite.
- **Actual:** la réponse est `success: true` mais le média affiché ne change pas — le nom est cherché dans une liste en cache. Trompeur. Le chemin d'upload réel (`/api/art/upload`) rafraîchit bien la liste et n'est pas affecté.
- **Status:** open — préexistant, hors périmètre du correctif vidéo.

---

## UX Test Results

### Mode Musée — lecture vidéo — 2026-10-14
- **Test method:** exploratoire sur matériel réel + inspection des captures d'écran de l'API.
- **Findings:**
  - *États définis* — **pass** : `starting` affiche « Démarrage de la lecture... », `error` affiche la cause réelle remontée par ffmpeg. Plus de rectangle noir muet ni de faux succès.
  - *Débordement du message d'erreur* — **medium, corrigé** : la ligne d'erreur sortait de l'écran des deux côtés, illisible au moment précis où elle sert. Troncature par `_fit_text()` + suppression du chemin absolu.
  - *Respect du ratio* — **pass** : source portrait 480×640 rendue en 270×360 centrée, bandes noires, sans déformation.
  - *Superposition du cartel* — **pass** : le cartel se dessine par-dessus la vidéo, ce qu'un player externe n'aurait jamais permis.
  - *Capture d'écran* — **pass** : `/screen` sur Telegram montre désormais la vidéo, et non plus un placeholder.
- **Recommendation:** no action. Validé sur l'écran physique par l'utilisateur.

### Passage à 30 fps — 2026-10-14
- **Test method:** mesure du débit réellement livré (comptage d'octets sur la commande live, `-re` compris), relevé CPU/load/température avec l'app en marche, lecture réelle via upload API.
- **Findings:**
  - *Débit tenu* — **pass sous condition** : 29,3 fps livrés sur une source 480p, **26,9 fps sur une mire 720p** (~10 % de frames perdues sur le pire cas synthétique). Pas de ralenti ni de désynchronisation observés, la dégradation est une perte de fluidité.
  - *Saturation CPU* — **medium, accepté** : load ≈ 4,0 sur 4 cœurs pendant la lecture (ffmpeg 1,44 cœur, app 49 % d'un cœur). Acceptable car le mode Musée est au premier plan et les fetches RSQA sont horaires.
  - *Sous-tension* — **medium, préexistant** : `vcgencmd get_throttled` = `0x50005`. **Contrôlé au repos, vidéo arrêtée : valeur identique** — l'alim 1,2 A est en cause, pas la vidéo. Température 62 °C, donc pas un problème thermique. Voir `BUG-005`.
  - *Non-régression* — **pass** : lecture, suppression en cours de lecture, absence de zombie et d'orphelin re-vérifiées après le passage à 30 fps.
- **Recommendation:** ship. Repasser `TARGET_FPS` à 15 est un correctif à une ligne si la marge devient insuffisante.

### [BUG-005] — Sous-tension et throttling permanents du Pi
- **Severity:** medium
- **Scenario:** `vcgencmd get_throttled` sur le Pi, à tout moment.
- **Expected:** `0x0`.
- **Actual:** `0x50005` — sous-tension et throttling, actifs et historiques, **y compris au repos**.
- **Root cause:** alimentation USB 1,2 A sous-dimensionnée pour un Pi 3 Model B.
- **Status:** open — préexistant, antérieur au travail sur la vidéo. Sans effet visible aujourd'hui, mais il mange la marge que le décodage à 30 fps vient de consommer. Correctif : alimentation 2,5 A.

### Upload nommé, sans IA, et refus de doublon — 2026-10-14
- **Threat model:** le titre vient d'un message Telegram et devient un nom de fichier (traversée de chemin, caractères de contrôle, encodage) ; `cartel_set` écrit un fichier désigné par un nom externe ; `X-On-Conflict: replace` écrase une œuvre existante.
- **Tests run:** upload titré accentué, doublon, remplacement, `cartel_set`, upload titré **avec** IA pour vérifier la survie du titre — tous au `curl` contre le musée réel, puis parcours complet depuis le routeur du bot.
- **Result:** **pass**.
- **Findings:**
  - *Traversée de chemin* — **non exploitable** : `_ascii_stem()` retire tout caractère hors `[\w\s-]` après repli des accents, donc `/` et `..` ne survivent pas ; `set_cartel()` et `delete_media()` partagent en plus `_resolve_media()`, qui exige que le chemin résolu ait `arts/` pour parent direct.
  - *Encodage d'en-tête* — **low, corrigé** : les en-têtes de texte libre sont percent-encodés à l'émission et décodés ici. Le défaut préexistait sur `X-Filename`.
  - *Écrasement* — **pass par conception** : `replace` n'est jamais le défaut. Sans en-tête explicite, un upload titré est refusé et un upload sans titre est suffixé.
  - *Titre réécrit par l'IA* — **medium, corrigé** : Gemini a réellement renommé « Mon Titre à Moi » en « Symphonie chromatique du néant cathodique » pendant les essais. Le verrou `titre_verrouille` est désormais restauré avant l'écriture du cache, et vérifié : « Essai Verrou » est ressorti intact avec un artiste rempli par l'IA.
  - *Abandons invisibles* — **low, corrigé** : deux chemins d'abandon de la génération de cartel ne journalisaient rien, ce qui a rendu un diagnostic inutilement long pendant cette session. Ils tracent désormais leur raison.

### Renommage d'œuvre — 2026-10-15
- **Threat model:** le nouveau nom vient d'un message Telegram (traversée de chemin, nom vide) ; un renommage peut écraser une autre œuvre ; une vidéo en lecture tient l'ancien inode.
- **Tests run:** renommage nominal avec titre accentué, vers un nom déjà pris, vers son propre nom, avec un titre sans caractère utilisable, et avec `../../etc/passwd` comme cible.
- **Result:** **pass**.
- **Findings:**
  - *Traversée de chemin* — **non exploitable** : `_resolve_media()` refuse toute cible hors `arts/` (vérifié : `../../etc/passwd` → « Chemin de fichier refusé »), et `_ascii_stem()` ne laisse survivre ni `/` ni `..` dans le nom produit.
  - *Écrasement* — **pass** : un nom déjà pris renvoie 409 sans rien déplacer.
  - *Nom vide* — **pass** : un titre sans caractère utilisable est refusé avant tout déplacement.
  - *Lecteur orphelin* — **pass par conception** : la lecture est arrêtée avant le renommage puis relancée sur le nouveau chemin.

---
## QA CHANGE LOG

### 2026-10-14 — Passage de la vidéo à 30 fps
**Tested:** débit livré à 15 et 30 fps sur sources 480p et 720p, CPU/load/température sous lecture, non-régression du cycle lecture → suppression, état d'alimentation.
**Result:** **conditional ship** — la cadence est tenue sur une source ordinaire, dégradée d'environ 10 % sur une source 720p très détaillée, et la machine tourne à saturation.
**Action taken:** changement conservé et déployé. `BUG-005` (sous-tension) ouvert et documenté comme préexistant. Retour à 15 fps identifié comme correctif à une ligne.


### 2026-10-14 — Audit de la lecture vidéo (réécriture par pipe ffmpeg)
**Tested:** lancement nominal (portrait et paysage), fichier tronqué, fichier aléatoire, suppression en cours de lecture, process résiduels, zombies, empreinte mémoire, lisibilité des états d'attente et d'erreur.
**Result:** **ship** — après correction de BUG-002 et du débordement du message d'erreur, tous deux trouvés et corrigés pendant l'audit.
**Action taken:** BUG-001 et BUG-002 corrigés en 2.5.1 et vérifiés sur matériel. BUG-003 : risque accepté, binding local. BUG-004 : différé, préexistant.

### 2026-10-14 — QA.md initialisé
**Tested:** —
**Result:** —
**Action taken:** scaffold du fichier, modèle de menaces initial documenté.

### 2026-10-14 — v2.6 : nommage, confidentialité, cartel manuel
**Tested:** contrat d'upload (titre, sans-IA, conflit, remplacement), `cartel_set`, survie du titre face à Gemini, garde-fous de chemin — au `curl` sur le Pi puis depuis le routeur du bot.
**Result:** **ship**.
**Action taken:** livré et déployé. Deux défauts trouvés et corrigés pendant l'audit (titre réécrit par l'IA ; abandons de cartel non journalisés).

### 2026-10-15 — v2.7 : renommage d'œuvre
**Tested:** cas nominal et quatre cas limites (nom pris, nom identique, nom invalide, traversée de chemin), au curl contre le musée réel puis depuis le routeur du bot.
**Result:** **ship**.
**Action taken:** livré et déployé.
