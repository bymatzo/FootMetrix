# -*- coding: utf-8 -*-
"""
Created on Thu May 15 10:18:00 2025

@author: darta
"""

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from openpyxl import load_workbook
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
import os

# === 1. Charger les fichiers Excel ===
fichier_entrainement = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Suivi Blessures Joueurs/Documents/FICHIER MERE GPS.xlsx"
fichier_matchs = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Suivi Blessures Joueurs/Documents/MATCHS FICHIER MERE GPS.xlsx"
fichier_info = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Suivi Blessures Joueurs/Documents/Infojoueurs.xlsx"
fichier_sortie = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Suivi Blessures Joueurs/Documents/testcode.xlsx"
fichier_acwr = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Suivi Blessures Joueurs/Documents/acwr_preoccupants.xlsx"

# === 2. Charger les feuilles ===
df_match = pd.read_excel(fichier_matchs, sheet_name="Worksheet")
df_entrainement = pd.read_excel(fichier_entrainement, sheet_name="Worksheet")
df_info = pd.read_excel(fichier_info, sheet_name="DETAIL JOUEURS")
df_blessure = pd.read_excel(fichier_info, sheet_name="BLESSURES JOUEURS")

# === 3. Marquer l'origine des données ===
df_match["Origine"] = "match"
df_entrainement["Origine"] = "entrainement"

# === 4. Fusionner les deux sources GPS ===
df = pd.concat([df_match, df_entrainement], ignore_index=True)

# === 5. Normaliser les postes ===
poste_mapping = {
    "DC": "DC", "EXC GCH": "DC", "EXC": "DC",
    "LAT G": "LAT GCH", "LAT GCH": "LAT GCH", "LAT GCJ": "LAT GCH", "PISONT GCH": "LAT GCH", "PISTON GCH": "LAT GCH",
    "LAT DT": "LAT DT", "PISTON DT": "LAT DT",
    "MIL OFF": "MIL OFF", "MIL EXC": "MIL OFF",
    "MIL DEF": "MIL DEF", "MIL DEL": "MIL DEF", "MILIEU DEF": "MIL DEF", "MIIL DEF": "MIL DEF",
    "ATT": "ATT", "FC": "ATT"
}
df['Poste normalisé'] = df['Poste joué'].map(poste_mapping)

# === 6. Ajouter l'âge depuis df_info ===
df = df.merge(df_info[['Nom joueur', 'Age']], left_on='Nom de joueur', right_on='Nom joueur', how='left')

# === 7. Catégoriser les âges ===
def get_tranche(age):
    if pd.isna(age):
        return "Inconnu"
    elif 17 <= age <= 20:
        return "17-20"
    elif 21 <= age <= 24:
        return "21-24"
    elif 25 <= age <= 28:
        return "25-28"
    elif 29 <= age <= 32:
        return "29-32"
    elif age >= 33:
        return "33+"
    else:
        return "Inconnu"
df["Tranche d'âge"] = df["Age"].apply(get_tranche)

# === 8. Convertir les dates ===
for df_temp, cols in [(df, ['Activity Date']), (df_blessure, ['Début blessure', 'Fin blessure'])]:
    for col in cols:
        df_temp[col] = pd.to_datetime(df_temp[col], errors='coerce')
        df_temp[col] = df_temp[col].apply(lambda x: x.tz_localize(None) if pd.notna(x) and hasattr(x, 'tz_localize') else x)
        
# === 9. Définition des indicateurs ACWR ===

indicateurs = [
    "Distance (m)", "Distance HID (>15 km/h)", "Distance HID (>20 km/h)",
    "Distance par plage de vitesse (15-20 km/h)", "Distance par plage de vitesse (20-25 km/h)",
    "Distance par plage de vitesse (25-28 km/h)", "Distance par plage de vitesse (>28 km/h)",
    "# of Sprints (>25 km/h)",
    "Accélération maximale (m/s²)", "# of Accelerations (>3 m/s²)",
    "# of Decélerations (>3 m/s²)" ]

df = df.sort_values(by=["Nom de joueur", "Activity Date"])
df["Activity Date"] = pd.to_datetime(df["Activity Date"])
df_blessure["Début blessure"] = pd.to_datetime(df_blessure["Début blessure"])

# Dictionnaire final : un DataFrame par indicateur
df_par_indicateur = {}

for indicateur in indicateurs:
    acwr_data = []

    for _, row in df_blessure.iterrows():
        joueur = row["Nom joueur"]
        blessure_date = row["Début blessure"]

        if pd.isna(blessure_date):
            continue
        
        # Ignorer les blessures trop proches du début des données
        date_debut_donnees = pd.to_datetime("2024-08-27")
        
        if blessure_date <= date_debut_donnees + pd.Timedelta(days=28):
            continue


        df_joueur = df[df["Nom de joueur"] == joueur].copy()
        df_joueur = df_joueur[df_joueur["Activity Date"] < blessure_date]
        df_joueur = df_joueur.sort_values("Activity Date").reset_index(drop=True)

        if indicateur not in df_joueur.columns:
            continue

        # Pour les 7 jours avant la blessure
        for jours_avant in range(1, 8):
            d = blessure_date - pd.Timedelta(days=jours_avant)

            debut_aigue = d - pd.Timedelta(days=7)
            debut_chronique = d - pd.Timedelta(days=28)

            semaine_aigue = df_joueur[
                (df_joueur["Activity Date"] > debut_aigue) &
                (df_joueur["Activity Date"] <= d)
            ]

            semaine_chronique = df_joueur[
                (df_joueur["Activity Date"] > debut_chronique) &
                (df_joueur["Activity Date"] <= debut_aigue)
            ]
            
            # Vérifie si les deux fenêtres sont vides
            if semaine_aigue.empty or semaine_chronique.empty:
                continue  # impossible de calculer l'ACWR

            # Cas normal
            else:
                charge_aigue = semaine_aigue[indicateur].sum()
                charge_chronique = semaine_chronique[indicateur].sum() * 0.333

            # Si charge aiguë est nulle, ACWR est NaN
            if charge_aigue == 0 or pd.isna(charge_aigue):
                acwr = np.nan
                
            if charge_chronique == 0 or pd.isna(charge_chronique):
                acwr = np.nan
            else:
                acwr = charge_aigue / charge_chronique



            acwr_data.append({
                "Nom de joueur": joueur,
                "Jour avant blessure": jours_avant,
                "Date évaluation": d,
                "Date blessure": blessure_date,
                "ACWR": acwr,
                "Charge aigue": charge_aigue,
                "Charge chronique": charge_chronique
            })

    df_par_indicateur[indicateur] = pd.DataFrame(acwr_data)
    
df_acwr_risque = {}

for indicateur, df_indicateur in df_par_indicateur.items():
    df_filtré1 = df_indicateur[
        (df_indicateur["ACWR"] < 0.8) | (df_indicateur["ACWR"] > 1.3)
    ].copy()
    df_acwr_risque[indicateur] = df_filtré1

df_acwr_risque_total = pd.concat([
    df.assign(Indicateur=indicateur)
    for indicateur, df in df_acwr_risque.items()], ignore_index=True)

# Supprimer les doublons sur les 7 jours avant blessure avec mêmes valeurs
df_acwr_risque_total = (
    df_acwr_risque_total.sort_values("Jour avant blessure")  # Assure que le plus récent est en dernier
    .drop_duplicates(
        subset=[
            "Nom de joueur", 
            "Date blessure", 
            "Indicateur", 
            "ACWR", 
            "Charge aigue", 
            "Charge chronique"
        ],
        keep="last"
    )
    .reset_index(drop=True)
)

df_alertes = {}

def generer_alerte(acwr):
    if acwr < 0.5:
        return "🔵 Risque élevé de sous-charge sévère (ACWR < 0.5)"
    elif acwr > 2.0:
        return "🔴 Risque élevé de surcharge aiguë (ACWR > 2.0)"
    else:
        return "🟠 Risque modéré, à surveiller"

for indicateur, df_indicateur in df_par_indicateur.items():
    df_filtré = df_indicateur[
        (df_indicateur["ACWR"] < 0.8) | (df_indicateur["ACWR"] > 1.3)
    ].copy()

    df_filtré["Alerte"] = df_filtré["ACWR"].apply(generer_alerte)
    
    # Facultatif : ajoute une colonne pour identifier l’indicateur
    df_filtré["Indicateur"] = indicateur
    
    # Enregistre dans le dictionnaire avec un nom explicite
    df_alertes[indicateur] = df_filtré 

# === ALERTE TEXTE : Joueurs avec >3 jours à risque avant blessure ===

alertes_joueurs = []

for indicateur, df_indic in df_par_indicateur.items():
    # Filtrer uniquement les valeurs à risque
    df_risque = df_indic[(df_indic["ACWR"] < 0.5) | (df_indic["ACWR"] > 2)].copy()

    # Compter le nombre de jours à risque par blessure
    risque_groupé = df_risque.groupby(["Nom de joueur", "Date blessure"]).size().reset_index(name="Jours à risque")

    # Garder uniquement les cas avec plus de 3 jours à risque
    risque_concerne = risque_groupé[risque_groupé["Jours à risque"] > 5]

    for _, row in risque_concerne.iterrows():
        joueur = row["Nom de joueur"]
        date_blessure = row["Date blessure"].strftime("%d/%m/%Y")
        nb_jours = row["Jours à risque"]

        texte = (f"⚠️ Joueur {joueur} a présenté un risque élevé ({nb_jours} jours d'ACWR anormal) "
                 f"dans les 7 jours précédant sa blessure du {date_blessure} pour l’indicateur : {indicateur}.")
        alertes_joueurs.append(texte)

# Affichage des alertes
for alerte in alertes_joueurs:
    print(alerte)

# Créer un DataFrame à partir de la liste de textes
df_alertes_excel = pd.DataFrame({
    "Alerte": alertes_joueurs
})

# Spécifie le chemin de sauvegarde
chemin_excel = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Suivi Blessures Joueurs/Documents/alertes_joueurs.xlsx"

# Enregistrement en Excel
df_alertes_excel.to_excel(chemin_excel, index=False)

print(f"✅ Fichier Excel enregistré : {chemin_excel}")

    
    
    
    
    
    


# Créer un dossier de sortie pour les graphiques
dossier_graphs = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques ACWR"
os.makedirs(dossier_graphs, exist_ok=True)

for indicateur, df_alertes_indic in df_alertes.items():
    # Compter les types d’alertes
    counts = df_alertes_indic["Alerte"].value_counts()

    if counts.empty:
        continue  # Sauter les indicateurs sans alertes

    # Définir les couleurs
    couleurs = {
        "🔵 Risque élevé de sous-charge sévère (ACWR < 0.5)": "#3498db",
        "🟠 Risque modéré, à surveiller": "#f39c12",
        "🔴 Risque élevé de surcharge aiguë (ACWR > 2.0)": "#e74c3c"
    }
    couleurs_utilisées = [couleurs[alerte] for alerte in counts.index]

    # Tracer le camembert
    plt.figure(figsize=(6, 6))
    plt.pie(counts, labels=counts.index, colors=couleurs_utilisées, autopct='%1.1f%%', startangle=140)
    plt.title(f"Répartition des alertes ACWR - {indicateur}", fontsize=12)
    plt.axis('equal')

    # Sauvegarde
    nom_fichier = f"{indicateur.replace('/', '_').replace('>', 'sup').replace('<', 'inf').replace(' ', '_')}.png"
    plt.savefig(os.path.join(dossier_graphs, nom_fichier), bbox_inches='tight')

    # Affichage interactif dans un onglet matplotlib
    plt.show()


df_duree = df_blessure[["Nom joueur", "Durée blessure"]]
df_age = df_info[["Nom joueur", "Age"]]

# Fusion
df_merged = pd.merge(df_duree, df_age, on="Nom joueur", how="left")
df_merged = df_merged.dropna(subset=["Age", "Durée blessure"])
df_merged["Tranche d'âge"] = df_merged["Age"].apply(get_tranche)

# Tracer le boxplot
plt.figure(figsize=(10, 6))
ordre_tranches = ["17-20", "21-24", "25-28", "29-32", "33+"]
sns.boxplot(data=df_merged, x="Tranche d'âge", y="Durée blessure", palette="Set2", order=ordre_tranches)

plt.title("Durée des blessures selon la tranche d'âge")
plt.xlabel("Tranche d'âge")
plt.ylabel("Durée de blessure (jours)")
plt.grid(True)
plt.ylim(0, 40)  # Limiter l’axe Y
plt.tight_layout()

# Sauvegarde
dossier_graphs = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques AGE"
os.makedirs(dossier_graphs, exist_ok=True)

chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques AGE/duree_blessures_par_tranche_age.png"
plt.savefig(chemin_fichier, bbox_inches="tight")

plt.show()


# Mapper tranche d'âge vers un âge moyen
tranche_to_mean_age = {
    "17-20": 18.5,
    "21-24": 22.5,
    "25-28": 26.5,
    "29-32": 30.5,
    "33+": 35
}

df_merged["Age_moyen_tranche"] = df_merged["Tranche d'âge"].map(tranche_to_mean_age)

# Corrélation avec la durée de blessure
correlation_duree = df_merged["Age_moyen_tranche"].corr(df_merged["Durée blessure"])
print(f"Corrélation entre tranche d'âge et durée de blessure : {correlation_duree:.2f}")

# Tous les joueurs et leur tranche
df_joueurs = df_info[["Nom joueur", "Age"]].copy()
df_joueurs["Tranche d'âge"] = df_joueurs["Age"].apply(get_tranche)

# Nb total de joueurs par tranche
joueurs_par_tranche = df_joueurs["Tranche d'âge"].value_counts()

# Nb total de blessures par tranche
blessures_par_tranche = df_merged["Tranche d'âge"].value_counts()

# Fréquence normalisée
frequence_blessure = (blessures_par_tranche / joueurs_par_tranche).dropna()

# Construire un DataFrame
df_frequence = frequence_blessure.reset_index()
df_frequence.columns = ["Tranche d'âge", "Fréquence de blessure"]

# Ajouter âge moyen
df_frequence["Age_moyen_tranche"] = df_frequence["Tranche d'âge"].map(tranche_to_mean_age)

# Corrélation
correlation_frequence = df_frequence["Age_moyen_tranche"].corr(df_frequence["Fréquence de blessure"])
print(f"Corrélation entre tranche d'âge et fréquence de blessure : {correlation_frequence:.2f}")

plt.figure(figsize=(8, 5))
sns.regplot(
    data=df_frequence,
    x="Age_moyen_tranche",
    y="Fréquence de blessure",
    scatter_kws={"s": 60, "color": "blue"},
    line_kws={"color": "red"},
)

plt.title("Corrélation entre l'âge moyen des tranches et la fréquence de blessure")
plt.xlabel("Âge moyen de la tranche")
plt.ylabel("Fréquence de blessure (%)")
plt.grid(True)
plt.tight_layout()
chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques AGE/correlation_age_frequence_blessure.png"
plt.savefig(chemin_fichier)
plt.show()




df["Blessé"] = False
for _, row in df_blessure.iterrows():
    joueur = row["Nom joueur"]
    date_blessure = row["Début blessure"]
    if pd.notna(date_blessure):
        # On marque comme blessé les données entre date_blessure-15j et date_blessure (pour la période la plus large)
        mask = (
            (df["Nom de joueur"] == joueur) &
            (df["Activity Date"] >= date_blessure - pd.Timedelta(days=15)) &
            (df["Activity Date"] < date_blessure)
        )
        df.loc[mask, "Blessé"] = True

def calc_moyennes_par_joueur(jours):
    moyennes = []
    joueurs = df["Nom de joueur"].unique()
    
    for joueur in joueurs:
        df_joueur = df[df["Nom de joueur"] == joueur].sort_values("Activity Date")
        blessures = df_blessure[df_blessure["Nom joueur"] == joueur]["Début blessure"].dropna()
        
        # Moyenne blessés (sur toutes les blessures de ce joueur)
        valeurs_blessés = []
        for date in blessures:
            fenetre = df_joueur[
                (df_joueur["Activity Date"] >= date - pd.Timedelta(days=jours)) &
                (df_joueur["Activity Date"] < date)
            ]
            if not fenetre.empty:
                valeurs_blessés.append(fenetre[indicateurs].mean())
        
        if valeurs_blessés:
            moy_blessé = pd.concat(valeurs_blessés, axis=1).mean(axis=1)
            moyennes.append({"Nom de joueur": joueur, "Blessé": True, **moy_blessé.to_dict()})
        
        # Moyenne non blessé : moyenne sur les mêmes jours pour les périodes sans blessure (exclure les fenêtres blessées)
        # Ici on prend toutes les dates d'activité du joueur hors période blessure et calcule moyenne glissante sur "jours"
        fenetre_non_blessee = df_joueur[~df_joueur["Blessé"]]
        if len(fenetre_non_blessee) >= jours:
            # moyenne simple sur les derniers jours disponibles hors blessure
            moy_non_blessé = fenetre_non_blessee.tail(jours)[indicateurs].mean()
            moyennes.append({"Nom de joueur": joueur, "Blessé": False, **moy_non_blessé.to_dict()})

    return pd.DataFrame(moyennes)

# Calcul des moyennes pour 7j et 15j
df_moy_7j = calc_moyennes_par_joueur(7)
df_moy_15j = calc_moyennes_par_joueur(15)


def calcul_diff_pourcentage(df_moy):
    moy_blesses = df_moy[df_moy["Blessé"] == True][indicateurs].mean()
    moy_non_blesses = df_moy[df_moy["Blessé"] == False][indicateurs].mean()
    variation_pct = ((moy_blesses - moy_non_blesses) / moy_non_blesses) * 100
    return pd.DataFrame(variation_pct, columns=["Variation en %"])

# Calcul des variations
heatmap_7j = calcul_diff_pourcentage(df_moy_7j)
heatmap_15j = calcul_diff_pourcentage(df_moy_15j)

# Trier les indicateurs par variation croissante
heatmap_7j = heatmap_7j.sort_values(by="Variation en %", ascending=True)
heatmap_15j = heatmap_15j.sort_values(by="Variation en %", ascending=True)

# Affichage en 2 graphiques séparés

plt.figure(figsize=(10, 8))
sns.heatmap(heatmap_7j.T, annot=True, cmap="coolwarm", center=0, fmt=".1f")
plt.title("Variation % indicateurs blessés vs non blessés (7 jours avant blessure)")
plt.ylabel("Indicateurs")

dossier_graphs = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Indicateurs"
os.makedirs(dossier_graphs, exist_ok=True) 

chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Indicateurs/variation_indicateur_7j.png"
plt.savefig(chemin_fichier)
plt.show()

plt.figure(figsize=(10, 8))
sns.heatmap(heatmap_15j.T, annot=True, cmap="coolwarm", center=0, fmt=".1f")
plt.title("Variation % indicateurs blessés vs non blessés (15 jours avant blessure)")
plt.ylabel("Indicateurs")


chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Indicateurs/variation_indicateur_15j.png"
plt.savefig(chemin_fichier)
plt.show()

indicateurs_monotony = [
    "Distance (m)", "Distance HID (>15 km/h)", "Distance HID (>20 km/h)",
    "Distance par plage de vitesse (15-20 km/h)", "Distance par plage de vitesse (20-25 km/h)",
    "Distance par plage de vitesse (25-28 km/h)", "Distance par plage de vitesse (>28 km/h)",
    "# of Sprints (>25 km/h)", "# of Sprints (>28 km/h)", "# of Accelerations (>3 m/s²)", "# of Accelerations (>5 m/s²)",
    "# of Decélerations (>3 m/s²)", "# of Decélerations (>5 m/s²)"
]

df = df.sort_values(by=["Nom de joueur", "Activity Date"])
df["Activity Date"] = pd.to_datetime(df["Activity Date"])
df_blessure["Début blessure"] = pd.to_datetime(df_blessure["Début blessure"])

df_monotony_data = {}

for indicateur in indicateurs_monotony:
    monotony_rows = []

    for _, blessure_row in df_blessure.iterrows():
        joueur_blessé = blessure_row["Nom joueur"]
        date_blessure = blessure_row["Début blessure"]

        if pd.isna(date_blessure):
            continue

        date_debut_donnees = pd.to_datetime("2024-08-27")
        if date_blessure <= date_debut_donnees + pd.Timedelta(days=14):
            continue

        df_joueur_blessé = df[
            (df["Nom de joueur"] == joueur_blessé) &
            (df["Activity Date"] < date_blessure)
        ].copy().sort_values("Activity Date").reset_index(drop=True)

        if indicateur not in df_joueur_blessé.columns:
            continue

        for jours_avant_blessure in range(1, 8):
            date_eval_monotony = date_blessure - pd.Timedelta(days=jours_avant_blessure)

            fenetre_7j = df_joueur_blessé[
                (df_joueur_blessé["Activity Date"] > date_eval_monotony - pd.Timedelta(days=7)) &
                (df_joueur_blessé["Activity Date"] <= date_eval_monotony)
            ]

            if len(fenetre_7j) >= 3:
                valeurs_indicateur = fenetre_7j[indicateur].dropna()
                moyenne_7j = valeurs_indicateur.mean()
                ecart_type_7j = valeurs_indicateur.std()

                monotony_score = moyenne_7j / ecart_type_7j if ecart_type_7j != 0 and not np.isnan(ecart_type_7j) else np.nan
                strain_score = valeurs_indicateur.sum() * monotony_score if not np.isnan(monotony_score) else np.nan

                monotony_rows.append({
                    "Nom de joueur": joueur_blessé,
                    "Jour avant blessure": jours_avant_blessure,
                    "Date évaluation": date_eval_monotony,
                    "Date blessure": date_blessure,
                    "Monotony": monotony_score,
                    "Strain": strain_score
                })

    df_monotony_data[indicateur] = pd.DataFrame(monotony_rows)

# Identification des cas à risque
df_monotony_risque = {}

for indicateur, df_monotony in df_monotony_data.items():
    seuil_strain = df_monotony["Strain"].quantile(0.9)
    df_filtré_monotony = df_monotony[
        (df_monotony["Monotony"] > 2.0) | (df_monotony["Strain"] > seuil_strain)
    ].copy()
    df_monotony_risque[indicateur] = df_filtré_monotony

# Fusion de tous les cas à risque
df_monotony_alertes_total = pd.concat([
    df_risque.assign(Indicateur=indicateur)
    for indicateur, df_risque in df_monotony_risque.items()
], ignore_index=True)

# Nettoyage : tri et suppression des doublons
df_monotony_alertes_total = (
    df_monotony_alertes_total.sort_values("Jour avant blessure")
    .drop_duplicates(
        subset=["Nom de joueur", "Date blessure", "Indicateur", "Monotony", "Strain"],
        keep="last"
    )
    .reset_index(drop=True)
)

# Fonctions d'alerte
def generer_alerte_monotony(monotony):
    if monotony > 2.5:
        return "🔴 Monotony très élevée (>2.5)"
    elif monotony > 2.0:
        return "🟠 Monotony élevée (>2.0)"
    else:
        return "✅ OK"

def generer_alerte_strain(strain, indicateur):
    if indicateur.startswith("#"):
        if strain > 300:
            return "🔴 Strain très élevé (événements >300)"
        elif strain > 50:
            return "🟠 Strain élevé (événements >50)"
    else:
        if strain > 130000:
            return "🔴 Strain très élevé (distance >130k)"
        elif strain > 80000:
            return "🟠 Strain élevé (distance >80k)"
    return "✅ OK"

# Application des alertes
df_monotony_alertes_total["Alerte_Monotony"] = df_monotony_alertes_total["Monotony"].apply(
    generer_alerte_monotony
)

df_monotony_alertes_total["Alerte_Strain"] = df_monotony_alertes_total.apply(
    lambda row: generer_alerte_strain(row["Strain"], row["Indicateur"]),
    axis=1
)


# Créer un dossier pour les graphiques Monotony
dossier_graphs_monotony = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques Monotony"
os.makedirs(dossier_graphs_monotony, exist_ok=True)

# Filtrage des seules alertes (hors "✅ OK")
df_monotony_alertes = df_monotony_alertes_total[
    df_monotony_alertes_total["Alerte_Monotony"] != "✅ OK"
]

# Compter les alertes par indicateur et par type d’alerte
compte_alertes = df_monotony_alertes.groupby(["Indicateur", "Alerte_Monotony"]).size().unstack(fill_value=0)

# Réorganiser pour forcer l’ordre des couleurs
ordre_alertes = ["🟠 Monotony élevée (>2.0)", "🔴 Monotony très élevée (>2.5)"]
compte_alertes = compte_alertes.reindex(columns=ordre_alertes, fill_value=0)

# Tracer le graphique en barres
compte_alertes.plot(kind='bar', stacked=False, color=["#f39c12", "#e74c3c"], figsize=(12, 6))

plt.title("Nombre d’alertes Monotony par indicateur", fontsize=14)
plt.xlabel("Indicateur")
plt.ylabel("Nombre d'alertes")
plt.xticks(rotation=45, ha='right')
plt.legend(title="Niveau d’alerte")
plt.tight_layout()

# Sauvegarde
plt.savefig(os.path.join(dossier_graphs_monotony, "Alertes_Monotony_par_indicateur.png"), bbox_inches="tight")
plt.show()

# Créer un dossier pour les graphiques Strain
dossier_graphs_strain = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques Strain"
os.makedirs(dossier_graphs_strain, exist_ok=True)

# Filtrage des alertes uniquement (hors "✅ OK")
df_strain_alertes = df_monotony_alertes_total[
    df_monotony_alertes_total["Alerte_Strain"] != "✅ OK"
]

# Compter les alertes par indicateur et par type d’alerte
compte_alertes_strain = df_strain_alertes.groupby(["Indicateur", "Alerte_Strain"]).size().unstack(fill_value=0)

# Réorganiser les colonnes dans l’ordre des niveaux de risque
ordre_alertes_strain = ["🟠 Strain élevé (événements >50)", "🔴 Strain très élevé (événements >300)",
                        "🟠 Strain élevé (distance >80k)", "🔴 Strain très élevé (distance >130k)"]
# Garder uniquement les colonnes présentes dans les données
colonnes_presentes = [col for col in ordre_alertes_strain if col in compte_alertes_strain.columns]
compte_alertes_strain = compte_alertes_strain.reindex(columns=colonnes_presentes, fill_value=0)

# Couleurs associées
couleurs_strain = {
    "🟠 Strain élevé (événements >50)": "#f39c12",
    "🔴 Strain très élevé (événements >300)": "#e74c3c",
    "🟠 Strain élevé (distance >80k)": "#f39c12",
    "🔴 Strain très élevé (distance >130k)": "#e74c3c",
}
couleurs_utilisées = [couleurs_strain[col] for col in colonnes_presentes]

# Tracer le graphique
compte_alertes_strain.plot(kind='bar', stacked=False, color=couleurs_utilisées, figsize=(12, 6))

plt.title("Nombre d’alertes Strain par indicateur", fontsize=14)
plt.xlabel("Indicateur")
plt.ylabel("Nombre d'alertes")
plt.xticks(rotation=45, ha='right')
plt.legend(title="Niveau d’alerte")
plt.tight_layout()

# Sauvegarde
plt.savefig(os.path.join(dossier_graphs_strain, "Alertes_Strain_par_indicateur.png"), bbox_inches="tight")
plt.show()

plt.figure(figsize=(14, 6))
sns.boxplot(data=df_monotony_alertes_total, x="Indicateur", y="Monotony", palette="Set3")
plt.xticks(rotation=45, ha='right')
plt.title("Distribution des scores de Monotony par indicateur")
plt.ylabel("Score de Monotony")
plt.xlabel("Indicateur")
plt.ylim(0, 6)
plt.tight_layout()
chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques Monotony/distribution_scores_monotony.png"
plt.savefig(chemin_fichier)
plt.show()




monotony_blesses = []
monotony_non_blesses = []

for indicateur in indicateurs_monotony:
    for _, row in df_blessure.iterrows():
        joueur = row["Nom joueur"]
        date_blessure = row["Début blessure"]
        
        df_joueur = df[df["Nom de joueur"] == joueur].copy().sort_values("Activity Date")
        if indicateur not in df_joueur.columns:
            continue
        
        # Calcul monotony sur les 15 jours avant blessure, jours_avant = 1 à 15
        for jours_avant in range(1, 16):
            date_eval = date_blessure - pd.Timedelta(days=jours_avant)
            fenetre_7j = df_joueur[
                (df_joueur["Activity Date"] > date_eval - pd.Timedelta(days=7)) & 
                (df_joueur["Activity Date"] <= date_eval)
            ]
            if len(fenetre_7j) < 3:
                continue
            vals = fenetre_7j[indicateur].dropna()
            moy = vals.mean()
            std = vals.std()
            monotony = moy / std if std != 0 and not np.isnan(std) else np.nan
            
            monotony_blesses.append({
                "Indicateur": indicateur,
                "Jour avant blessure": jours_avant,
                "Monotony": monotony,
                "Blessé": True
            })
            
    # Joueurs non blessés - simulation dates "blessure"
    for joueur in df["Nom de joueur"].unique():
        df_joueur = df[df["Nom de joueur"] == joueur].copy()
        blessures_joueur = df_blessure[df_blessure["Nom joueur"] == joueur]["Début blessure"].dropna()
        # Exclure période proche blessures
        for date in blessures_joueur:
            mask = (df_joueur["Activity Date"] >= date - pd.Timedelta(days=15)) & (df_joueur["Activity Date"] <= date)
            df_joueur = df_joueur[~mask]
        df_joueur = df_joueur.sort_values("Activity Date").reset_index(drop=True)
        
        if len(df_joueur) < 35:
            continue
        
        # Simuler dates blessure tous les 15 jours
        for i in range(0, len(df_joueur) - 35, 15):
            date_simulee = df_joueur.iloc[i + 35]["Activity Date"]
            
            for jours_avant in range(1, 16):
                date_eval = date_simulee - pd.Timedelta(days=jours_avant)
                fenetre_7j = df_joueur[
                    (df_joueur["Activity Date"] > date_eval - pd.Timedelta(days=7)) & 
                    (df_joueur["Activity Date"] <= date_eval)
                ]
                if len(fenetre_7j) < 3:
                    continue
                vals = fenetre_7j[indicateur].dropna()
                moy = vals.mean()
                std = vals.std()
                monotony = moy / std if std != 0 and not np.isnan(std) else np.nan
                
                monotony_non_blesses.append({
                    "Indicateur": indicateur,
                    "Jour avant blessure": jours_avant,
                    "Monotony": monotony,
                    "Blessé": False
                })

# Fusionner
df_monotony = pd.DataFrame(monotony_blesses + monotony_non_blesses)
df_monotony = df_monotony.dropna(subset=["Monotony"])

# Tracer par indicateur
for indicateur in df_monotony["Indicateur"].unique():
    df_plot = df_monotony[df_monotony["Indicateur"] == indicateur]
    df_moy = df_plot.groupby(["Jour avant blessure", "Blessé"])["Monotony"].mean().reset_index()
    
    plt.figure(figsize=(8,5))
    sns.lineplot(data=df_moy, x="Jour avant blessure", y="Monotony", hue="Blessé",
                 palette={True: "red", False: "blue"}, marker="o")
    plt.title(f"Monotony moyen - {indicateur}")
    plt.xlabel("Jour avant blessure")
    plt.ylabel("Monotony moyen")
    plt.gca().invert_xaxis()
    plt.grid(True)
    plt.tight_layout()
    plt.show()



# Assurer que la colonne 'Début blessure' est en datetime
df_blessure["Début blessure"] = pd.to_datetime(df_blessure["Début blessure"], errors='coerce')

# Créer une colonne "Mois_Année" (ex: Août 2024)
df_blessure["Mois_Année"] = df_blessure["Début blessure"].dt.to_period("M").dt.to_timestamp()

# Filtrer uniquement la période Août 2024 à Avril 2025
debut = pd.to_datetime("2024-08-01")
fin = pd.to_datetime("2025-04-30")
df_blessure_filtered = df_blessure[(df_blessure["Début blessure"] >= debut) & (df_blessure["Début blessure"] <= fin)]

# Grouper par Mois_Année
blessures_par_mois = df_blessure_filtered["Mois_Année"].value_counts().sort_index()
total_blessures = blessures_par_mois.sum()
pourcentage_par_mois = (blessures_par_mois / total_blessures * 100).round(1)

# Création du DataFrame pour affichage
df_mois_blessures = pd.DataFrame({
    "Mois_Année": pourcentage_par_mois.index,
    "Pourcentage de blessures": pourcentage_par_mois.values
})

# Affichage graphique
plt.figure(figsize=(12, 6))

# Affichage du barplot
sns.barplot(data=df_mois_blessures, x="Mois_Année", y="Pourcentage de blessures", palette="coolwarm")

# Ajout de la courbe de tendance
sns.regplot(data=df_mois_blessures, x=np.arange(len(df_mois_blessures)), y="Pourcentage de blessures", scatter=False, color='red', line_kws={'linestyle':'--', 'linewidth': 2})

# Définir les positions des barres et les étiquettes sur l'axe X
plt.xticks(ticks=np.arange(len(df_mois_blessures)), labels=df_mois_blessures["Mois_Année"].dt.strftime('%b %Y'), rotation=45)

plt.title("Répartition des blessures par mois (Août 2024 à Avril 2025)")
plt.ylabel("Pourcentage (%)")
plt.xlabel("Mois")
plt.grid(axis='y')
plt.tight_layout()

dossier_graphs = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques Blessures"
os.makedirs(dossier_graphs, exist_ok=True)

chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques Blessures/blessures_par_mois.png"
plt.savefig(chemin_fichier) 

plt.show()


# Graphique 4 : Heatmap des alertes par joueur et indicateur
pivot_alertes = df_acwr_risque_total.pivot_table(
    index="Nom de joueur", 
    columns="Indicateur", 
    values="ACWR", 
    aggfunc="count", 
    fill_value=0
)

plt.figure(figsize=(12, 8))
sns.heatmap(pivot_alertes, cmap="YlOrRd", annot=True, fmt=".0f")
plt.title("Nombre d'alertes ACWR par joueur et par indicateur", fontsize=14)
plt.xlabel("Indicateur")
plt.ylabel("Joueur")
plt.tight_layout()
chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques ACWR/nombre_alertes.png"
plt.savefig(chemin_fichier)
plt.show()    

# === Création de la heatmap ACWR moyen par joueur blessé et par indicateur ===

data_heatmap_acwr = []

for indicateur, df_indic in df_par_indicateur.items():
    df_7j = df_indic[df_indic["Jour avant blessure"] <= 7]
    moyennes_par_joueur = df_7j.groupby("Nom de joueur")["ACWR"].mean().reset_index()
    moyennes_par_joueur["Indicateur"] = indicateur
    data_heatmap_acwr.append(moyennes_par_joueur)

df_acwr_heatmap = pd.concat(data_heatmap_acwr)
heatmap_acwr_table = df_acwr_heatmap.pivot(index="Nom de joueur", columns="Indicateur", values="ACWR")
heatmap_acwr_table = heatmap_acwr_table.dropna(thresh=3)

# Couleurs : bleu (pour <0.8), blanc (entre 0.8 et 1.3), rouge (>1.3)
colors = ["blue", "white", "red"]
cmap = mcolors.LinearSegmentedColormap.from_list("custom_acwr", colors)

# Norme à deux pentes : centre entre 0.8 et 1.3
# On centre sur 1.05 (milieu entre 0.8 et 1.3)
norm = mcolors.TwoSlopeNorm(vmin=heatmap_acwr_table.min().min(),
                           vcenter=1.05,
                           vmax=heatmap_acwr_table.max().max())

plt.figure(figsize=(12, 8))
sns.heatmap(heatmap_acwr_table, annot=True, cmap=cmap, norm=norm, fmt=".2f", linewidths=0.5)
plt.title("ACWR moyen par joueur blessé et par indicateur (7 jours avant blessure)")
plt.xlabel("Indicateur")
plt.ylabel("Joueur")
plt.tight_layout()
chemin_fichier = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Graphiques ACWR/acwr_moyen.png"
plt.savefig(chemin_fichier)
plt.show()








































indicateurs_graph = [
    "Distance (m)", 
    "Distance HID (>15 km/h)", 
    "Distance HID (>20 km/h)",
    "Distance par plage de vitesse (15-20 km/h)", 
    "Distance par plage de vitesse (20-25 km/h)",
    "Distance par plage de vitesse (25-28 km/h)", 
    "# of Sprints (>25 km/h)", 
    "# of Accelerations (>3 m/s²)", 
    "# of Accelerations (>5 m/s²)",
    "# of Decélerations (>3 m/s²)", 
    "# of Decélerations (>5 m/s²)"
]

df_par_indicateur = {k: v for k, v in df_par_indicateur.items() if k in indicateurs_graph}

acwr_blesses = []
acwr_non_blesses = []

# Pour vérification de cohérence temporelle
derniere_date_gps = df.groupby("Nom de joueur")["Activity Date"].max()

for indicateur, df_indic in df_par_indicateur.items():
    if df_indic.empty:
        continue

    # ====== BLESSÉS ======
    for _, row in df_blessure.iterrows():
        joueur = row["Nom joueur"]
        date_blessure = row["Début blessure"]

        # ⚠️ Vérifie que les données GPS couvrent la période
        dernier_gps = derniere_date_gps.get(joueur)
        if pd.isna(dernier_gps) or (date_blessure > dernier_gps):
            continue

        df_joueur = df[df["Nom de joueur"] == joueur].copy().sort_values("Activity Date")

        for jours_avant in range(1, 8):
            d = date_blessure - pd.Timedelta(days=jours_avant)
            debut_aigue = d - pd.Timedelta(days=7)
            debut_chronique = d - pd.Timedelta(days=28)

            semaine_aigue = df_joueur[(df_joueur["Activity Date"] > debut_aigue) & (df_joueur["Activity Date"] <= d)]
            semaine_chronique = df_joueur[(df_joueur["Activity Date"] > debut_chronique) & (df_joueur["Activity Date"] <= debut_aigue)]

            if semaine_aigue.empty or semaine_chronique.empty:
                continue

            charge_aigue = semaine_aigue[indicateur].sum()
            charge_chronique = semaine_chronique[indicateur].sum() * 0.333

            if charge_aigue == 0 or charge_chronique == 0:
                continue

            acwr = charge_aigue / charge_chronique

            acwr_blesses.append({
                "Indicateur": indicateur,
                "Jour avant blessure": jours_avant,
                "ACWR": acwr,
                "Blessé": True,
                "Nom joueur": joueur,
                "Date blessure": date_blessure
            })

    # ====== NON BLESSÉS ======
    for joueur in df["Nom de joueur"].unique():
        df_joueur = df[df["Nom de joueur"] == joueur].copy()
        blessures_joueur = df_blessure[df_blessure["Nom joueur"] == joueur]["Début blessure"].dropna()

        for date in blessures_joueur:
            mask = (df_joueur["Activity Date"] >= date - pd.Timedelta(days=15)) & (df_joueur["Activity Date"] <= date)
            df_joueur = df_joueur[~mask]

        df_joueur = df_joueur.sort_values("Activity Date").reset_index(drop=True)

        if len(df_joueur) >= 35:
            for i in range(0, len(df_joueur) - 35, 15):
                date_simulee = df_joueur.iloc[i + 35]["Activity Date"]

                for jours_avant in range(1, 8):
                    d = date_simulee - pd.Timedelta(days=jours_avant)
                    debut_aigue = d - pd.Timedelta(days=7)
                    debut_chronique = d - pd.Timedelta(days=28)

                    semaine_aigue = df_joueur[(df_joueur["Activity Date"] > debut_aigue) & (df_joueur["Activity Date"] <= d)]
                    semaine_chronique = df_joueur[(df_joueur["Activity Date"] > debut_chronique) & (df_joueur["Activity Date"] <= debut_aigue)]

                    if semaine_aigue.empty or semaine_chronique.empty:
                        continue

                    charge_aigue = semaine_aigue[indicateur].sum()
                    charge_chronique = semaine_chronique[indicateur].sum() * 0.333

                    if charge_aigue == 0 or charge_chronique == 0:
                        continue

                    acwr = charge_aigue / charge_chronique

                    acwr_non_blesses.append({
                        "Indicateur": indicateur,
                        "Jour avant blessure": jours_avant,
                        "ACWR": acwr,
                        "Blessé": False
                    })

# ======= Fusion et nettoyage =======
df_acwr = pd.DataFrame(acwr_blesses + acwr_non_blesses)
df_acwr = df_acwr[df_acwr["ACWR"] <= 10]

# ======= Tracé par blessure individuelle =======

for blessure in df_acwr[df_acwr["Blessé"] == True][["Nom joueur", "Date blessure"]].drop_duplicates().itertuples(index=False):
    joueur, date_blessure = blessure

    for indicateur in df_acwr["Indicateur"].unique():
        df_joueur = df_acwr[
            (df_acwr["Blessé"] == True) &
            (df_acwr["Nom joueur"] == joueur) &
            (df_acwr["Date blessure"] == date_blessure) &
            (df_acwr["Indicateur"] == indicateur)
        ]

        if df_joueur.empty:
            continue

        df_moy = df_acwr[
            (df_acwr["Blessé"] == False) &
            (df_acwr["Indicateur"] == indicateur)
        ].groupby("Jour avant blessure")["ACWR"].mean().reset_index()

        # Tracé
        plt.figure(figsize=(8, 5))
        sns.lineplot(data=df_moy, x="Jour avant blessure", y="ACWR", label="Moyenne groupe", color="yellow", marker="o")
        sns.lineplot(data=df_joueur, x="Jour avant blessure", y="ACWR", label=f"{joueur}", color="violet", marker="o")
        plt.title(f"ACWR - {indicateur}\n{joueur} - blessure le {date_blessure.date()}")
        plt.xlabel("Jour avant blessure")
        plt.ylabel("ACWR")
        plt.gca().invert_xaxis()
        plt.grid(True)

        # Dossier et nom fichier
        dossier_joueur = os.path.join("graph_acwr", f"{joueur}_{date_blessure.date()}")
        os.makedirs(dossier_joueur, exist_ok=True)
        nom_fichier = f"{indicateur.replace('/', '_').replace('>', 'sup').replace('<', 'inf').replace(' ', '_')}.png"
        chemin_complet = os.path.join(dossier_joueur, nom_fichier)

        plt.tight_layout()
        plt.savefig(chemin_complet)
        plt.show()

  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
  
    
    

# ========== PARAMÈTRES ==========
indicateurs_graph = [ 
    "Distance (m)", 
    "Distance HID (>15 km/h)", 
    "Distance HID (>20 km/h)",
    "Distance par plage de vitesse (15-20 km/h)", 
    "Distance par plage de vitesse (20-25 km/h)",
    "Distance par plage de vitesse (25-28 km/h)", 
    "# of Sprints (>25 km/h)", 
    "# of Accelerations (>3 m/s²)", 
    "# of Accelerations (>5 m/s²)",
    "# of Decélerations (>3 m/s²)", 
    "# of Decélerations (>5 m/s²)"
]

dossier_graphs = "C:/Users/darta/OneDrive/Bureau/Stage FCBJ/Indicateurs"
os.makedirs(dossier_graphs, exist_ok=True)

resultats = []

# ========== BOUCLE PRINCIPALE ==========
for _, blessure in df_blessure.iterrows():
    joueur_blesse = blessure["Nom joueur"]
    date_blessure = blessure["Début blessure"]

    # Filtrer les 15 jours avant la blessure pour le joueur blessé
    df_blesse = df[(df["Nom de joueur"] == joueur_blesse) &
                   (df["Activity Date"] >= date_blessure - pd.Timedelta(days=15)) &
                   (df["Activity Date"] < date_blessure)].copy()
    
    # Calculer le jour relatif à la blessure (1 à 15)
    df_blesse["Jour avant blessure"] = (date_blessure - df_blesse["Activity Date"]).dt.days

    for _, row in df_blesse.iterrows():
        for indicateur in indicateurs_graph:
            if pd.notna(row[indicateur]):
                resultats.append({
                    "Jour avant blessure": row["Jour avant blessure"],
                    "Indicateur": indicateur,
                    "Valeur": row[indicateur],
                    "Blessé": True
                })

    # Tous les autres joueurs NON blessés autour de cette même période
    joueurs_autres = df["Nom de joueur"].unique()
    joueurs_autres = [j for j in joueurs_autres if j != joueur_blesse]

    for joueur in joueurs_autres:
        df_joueur = df[(df["Nom de joueur"] == joueur) &
                       (df["Activity Date"] >= date_blessure - pd.Timedelta(days=15)) &
                       (df["Activity Date"] < date_blessure)].copy()
        
        df_joueur["Jour avant blessure"] = (date_blessure - df_joueur["Activity Date"]).dt.days

        for _, row in df_joueur.iterrows():
            for indicateur in indicateurs_graph:
                if pd.notna(row[indicateur]):
                    resultats.append({
                        "Jour avant blessure": row["Jour avant blessure"],
                        "Indicateur": indicateur,
                        "Valeur": row[indicateur],
                        "Blessé": False
                    })

# ========== CONSTRUCTION DU DF FINAL ==========
df_resultats = pd.DataFrame(resultats)

# ========== GRAPHIQUES ==========
for indicateur in indicateurs_graph:
    df_indic = df_resultats[df_resultats["Indicateur"] == indicateur]

    df_moyennes = df_indic.groupby(["Jour avant blessure", "Blessé"])["Valeur"].mean().reset_index()

    plt.figure(figsize=(8, 5))
    sns.lineplot(data=df_moyennes, x="Jour avant blessure", y="Valeur", hue="Blessé",
                 palette={True: "red", False: "blue"}, marker="o")
    plt.title(f"Évolution moyenne - {indicateur}")
    plt.xlabel("Jour avant blessure")
    plt.ylabel("Valeur moyenne")
    plt.gca().invert_xaxis()
    plt.grid(True)
    plt.tight_layout()

    nom_fig = f"courbe_moy_{indicateur.replace('/', '_').replace('>', 'sup').replace('<', 'inf').replace(' ', '_')}.png"
    plt.savefig(os.path.join(dossier_graphs, nom_fig))
    plt.show()



























for indicateur, df_indic in df_monotony_data.items():
    if df_indic.empty:
        continue

    grouped = df_indic.groupby(["Nom de joueur", "Date blessure"])

    for (joueur, date_blessure), df_blessure_joueur in grouped:
        plt.figure(figsize=(10, 6))

        # Tracé du premier axe (Monotony)
        ax1 = plt.gca()
        ax1.plot(df_blessure_joueur["Jour avant blessure"], df_blessure_joueur["Monotony"],
                 color="orange", marker="o", label="Monotony")
        ax1.set_ylabel("Monotony", color="orange")
        ax1.tick_params(axis='y', labelcolor="orange")
        ax1.axhline(2, color='red', linestyle='--', label="Seuil Monotony = 2")

        # Tracé du second axe (Strain)
        ax2 = ax1.twinx()
        ax2.plot(df_blessure_joueur["Jour avant blessure"], df_blessure_joueur["Strain"],
                 color="blue", marker="s", label="Strain")
        ax2.set_ylabel("Strain", color="blue")
        ax2.tick_params(axis='y', labelcolor="blue")

        # Titres et axes
        plt.title(f"{joueur} - {indicateur}\nBlessure le {date_blessure.date()}")
        ax1.set_xlabel("Jours avant blessure")
        ax1.invert_xaxis()
        ax1.grid(True)

        # Créer dossier par blessure
        dossier_joueur = os.path.join("graph_monotony_strain", f"{joueur}_{date_blessure.date()}")
        os.makedirs(dossier_joueur, exist_ok=True)

        # Enregistrement
        nom_fichier = f"{indicateur.replace('/', '_').replace('>', 'sup').replace('<', 'inf').replace(' ', '_')}.png"
        chemin_complet = os.path.join(dossier_joueur, nom_fichier)
        plt.tight_layout()
        plt.savefig(chemin_complet)

        # Affichage direct dans éditeur
        plt.show()






































