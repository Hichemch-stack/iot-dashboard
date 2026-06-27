📘 README – AI Smart Environmental Monitoring Platform

🌍 Présentation du projet
AI Smart Environmental Monitoring Platform est une solution complète combinant :
Plain Text1IoT + Cloud + Big Data + Intelligence Artificielle + Dashboard Web2``Show more lines
Le projet permet de :

collecter des données environnementales via une station ESP32 simulée (Wokwi)
envoyer ces données vers ThingSpeak (cloud IoT)
analyser les données avec un backend Python Flask
appliquer des modèles d’intelligence artificielle
stocker les résultats dans MongoDB Atlas
visualiser les données via un dashboard professionnel


🧠 Fonctionnalités principales
✅ IoT (ESP32 + capteurs)

Température (DHT22)
Humidité
Température analogique (LM35)
Luminosité (LDR)
Mouvement (PIR)
Distance (HC-SR04)
Risk Score (calcul local)


✅ Cloud ThingSpeak

Stockage des données IoT (8 fields)
API REST JSON
Visualisation temps réel


✅ Backend IA (Flask + Python)

Traitement Pandas
Détection anomalies (Isolation Forest)
Prédiction température (Linear Regression)
Calcul :

ECI (Environmental Criticality Index)
EHI (Environment Health Index)


Data Quality Score
Multi-station logic
API REST complète


✅ MongoDB Atlas

Stockage Big Data cloud
Collections :

raw_sensor_data
processed_sensor_data
analytics_results




✅ Dashboard Pro v4

Données temps réel
Intelligence artificielle
Graphiques
Heatmap ECI
Timeline alertes IA
Multi-station monitoring
Dark Mode


🏗️ Architecture globale
Plain Text1ESP32 (Wokwi)2   ↓3ThingSpeak Cloud4   ↓5Backend Flask IA v26   ↓7Pandas + Scikit-learn8   ↓9MongoDB Atlas10   ↓11Dashboard Pro v412``Show more lines

📂 Structure du projet
Plain Text1Sujet7-AI-Platform/2│3├── ai_environment_server_v2_multistation.py4├── dashboard_pro_v4_dark_multistation.html5├── analytics_cache.json (fallback)6├── .env7├── requirements.txt8└── README.mdShow more lines

⚙️ Installation
1. Cloner ou ouvrir le projet
PowerShell1cd C:\Sujet7-AI-PlatformShow more lines

2. Activer l’environnement virtuel
PowerShell1.\venv\Scripts\activateShow more lines

3. Installer les dépendances
PowerShell1pip install flask flask-cors pandas numpy pymongo scikit-learn python-dotenv requests2 Show more lines

4. Configurer .env
PowerShellenv isn’t fully supported. Syntax highlighting is based on PowerShell.1THINGSPEAK_CHANNEL_ID=34060012THINGSPEAK_READ_API_KEY=XXXXXXXX3MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/4FLASK_HOST=127.0.0.15FLASK_PORT=50006 Show more lines

🚀 Exécution
▶️ 1. Lancer le backend IA
PowerShell1python ai_environment_server_v2_multistation.pyShow more lines
Accès :
Plain Text1http://127.0.0.1:5000Show more lines

▶️ 2. Lancer le dashboard
PowerShell1python -m http.server 80802``Show more lines
Ouvrir :
Plain Text1http://127.0.0.1:8080/dashboard_pro_v4_dark_multistation.htmlShow more lines

🔌 Endpoints API









































EndpointDescription/api/healthVérification backend/api/analyzeAnalyse IA complète/api/latestDernière donnée/api/statsStatistiques globales/api/timeseriesSérie temporelle/api/alertsAlertes IA/api/stationsMulti-station/api/station/<id>/timeseriesData par station

🏢 Multi-station Monitoring
Le projet inclut une simulation multi-station :





















StationZoneST-ASalle principaleST-BZone techniqueST-CZone extérieure
➡️ Permet de simuler une architecture scalable IoT.

🌙 Dark Mode

Activation via bouton
Persistant via localStorage
Mode clair / sombre


📊 Indicateurs intelligents
ECI (Environmental Criticality Index)
Plain Text10 - 35     → NORMAL235 - 70    → WARNING370 - 100   → CRITICALShow more lines

EHI (Environment Health Index)
Plain Text1EHI = 100 - ECI2 Show more lines

Data Quality Score
Évalue :

données manquantes
valeurs invalides
incohérences


🧪 Tests
✅ ThingSpeak connecté
✅ Backend Flask actif
✅ MongoDB Atlas connecté
✅ Dashboard fonctionnel
✅ Multi-station opérationnel
✅ IA active

⚠️ Limitations

Données simulées (Wokwi)
Modèle ML basique
Pas de sécurité API avancée
Dashboard local uniquement


🚀 Améliorations futures

✅ Notifications Telegram
✅ API sécurisée (JWT)
✅ Déploiement cloud
✅ Multi-stations réelles
✅ Prédiction avancée (TensorFlow)
✅ Export PDF automatique


👨‍💻 Auteur
CHEBBI Hichem

🎓 Projet académique
Projet réalisé dans le cadre de :
Plain Text1Sujet 7 – IoT Smart Monitoring + Big Data + AIShow more lines

✅ Résultat
Avec ce README, ton projet atteint :
Plain Text1Niveau professionnel ✅2Niveau soutenance ✅3Niveau GitHub ✅4``Show more lines

🔥 Si tu veux aller encore plus loin
Je peux te générer :
✅ requirements.txt optimal
✅ version GitHub propre du projet
✅ script d’installation automatique
✅ slides PowerPoint soutenance
✅ diagramme architecture (image pro)
