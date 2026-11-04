# Guide d'installation de FENIX (Français)

Environ **15 minutes**. Aucune connaissance technique requise ; suivez simplement les étapes dans l'ordre.

## Ce qu'il vous faut

| | |
|---|---|
| Ordinateur | Windows 10 ou 11 |
| Programme | Python 3.12 (gratuit) |
| Clé | Clé API Gemini (gratuite, obligatoire) |
| Facultatif | Clé API Groq (gratuite ; discussion plus rapide, meilleure reconnaissance vocale) |
| Facultatif | Clé API NVIDIA (gratuite ; discussion de secours quand Groq est épuisé) — https://build.nvidia.com |
| Facultatif | Clé API Tavily (quota mensuel gratuit ; meilleure recherche web) — https://app.tavily.com |

## 1. Télécharger FENIX

1. Sur la page GitHub, cliquez sur le bouton vert **Code** → **Download ZIP**.
2. Clic droit sur le ZIP → **Extraire tout**. Placez le dossier dans un endroit simple, ex. `Documents\fenix`.

## 2. Installer Python

1. Téléchargez **Python 3.12** sur https://www.python.org/downloads/.
2. Sur le premier écran de l'installateur, **cochez "Add python.exe to PATH"**, puis **Install Now**.

## 3. Obtenir votre clé Gemini

1. Allez sur https://aistudio.google.com/apikey et connectez-vous avec votre compte Google.
2. **Create API key** → copiez la clé. **Ne la partagez jamais**.
3. (Facultatif) Une clé Groq s'obtient sur https://console.groq.com/keys.

## 4. Lancer l'installation

1. Double-cliquez sur **`Setup.bat`** dans le dossier FENIX.
   - Si « Windows a protégé votre ordinateur » s'affiche : **Informations complémentaires → Exécuter quand même**.
2. Choisissez votre langue dans la fenêtre (1-6).
3. Si Python manque, l'installation le signale et propose de l'installer automatiquement.
4. Patientez pendant l'installation des paquets (5-10 minutes). Un raccourci **FENIX** est ajouté au bureau.

## 5. Démarrer FENIX et coller votre clé

- Double-cliquez sur l'icône **FENIX** du bureau.
- Au premier démarrage, une petite fenêtre **Clé API** s'ouvre : collez votre clé Gemini (et Groq si vous en avez une) puis cliquez sur **Enregistrer et démarrer**. Aucun fichier à modifier.
- Vous pourrez changer la langue dans **⚙️ Paramètres**.

## Utilisation rapide

| Quoi | Comment |
|---|---|
| Discussion écrite | Tapez en bas, **Entrée** |
| Discussion vocale | Bouton **🎤 Appuyer pour parler** ou **F9** |
| Joindre un fichier / une image | **📎**, glisser-déposer ou **Ctrl+V** |
| Mode | **Sûr** (discussion seule) · **Normal** (quotidien, demande avant le risqué) · **Devil** (recherche approfondie, rapports) |
| Arrêt d'urgence | **Ctrl+Alt+Q** ou souris 1,5 s dans le coin supérieur gauche |

Avant toute action risquée (suppression, arrêt, téléchargement…), FENIX **demande une approbation dans tous les modes**.

## Un problème ?

| Symptôme | Solution |
|---|---|
| « Python introuvable » | Réinstallez Python en cochant **Add python.exe to PATH**. |
| Erreur de clé / pas de réponse | Lancez **`Connection_Test.bat`** ; il indique la clé en cause. |
| Le micro n'entend rien | Lancez **`Microphone_Test.bat`**. Choisissez le bon micro dans les paramètres son de Windows. |
| La fenêtre ne s'ouvre pas | Démarrez avec **`Start_FENIX_Debug.bat`** ; le message d'erreur reste affiché. |
| Le mode veille ne marche pas | Il ne fonctionne que sous Windows ; relancez `Setup.bat`. |

Remarque : les scripts de test affichent leurs messages en turc.

## Sécurité

- `config.yaml` contient vos clés : **ne l'envoyez à personne et ne le mettez pas sur GitHub.**
- Le dossier `data` contient vos discussions et votre mémoire ; c'est personnel aussi.
- Si une clé a été exposée, **supprimez-la sur le site du fournisseur et créez-en une nouvelle**.
