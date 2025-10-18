# -*- coding: utf-8 -*-
"""
Created on Tue May 13 15:22:32 2025

@author: darta
"""

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from openpyxl import load_workbook
import matplotlib.dates as mdates
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

# === 9. Calcul ACWR et détection des cas préoccupants ===
indicateurs = [
    "Distance (m)", "Distance HID (>15 km/h)", "Distance HID (>20 km/h)",
    "Distance par plage de vitesse (15-20 km/h)", "Distance par plage de vitesse (20-25 km/h)",
    "Distance par plage de vitesse (25-28 km/h)", "Distance par plage de vitesse (>28 km/h)",
    "# of Sprints (>25 km/h)", "# of Sprints (>28 km/h)", "Vitesse max (km/h)",
    "Accélération maximale (m/s²)", "# of Accelerations (>3 m/s²)", "# of Accelerations (>5 m/s²)",
    "# of Decélerations (>3 m/s²)", "# of Decélerations (>5 m/s²)"
]

df = df.sort_values(by=["Nom de joueur", "Activity Date"])

# Dictionnaire des blessures par joueur
blessures_dict = {}
for _, row in df_blessure.iterrows():
    joueur_nom = row["Nom joueur"]
    debut = row["Début blessure"]
    if pd.notna(debut):
        if joueur_nom not in blessures_dict:
            blessures_dict[joueur_nom] = []
        blessures_dict[joueur_nom].append(debut)

acwr_preoccupants = []

for joueur in df['Nom de joueur'].unique():
    df_joueur = df[df['Nom de joueur'] == joueur].copy().sort_values("Activity Date").reset_index(drop=True)
    blessures_joueur = blessures_dict.get(joueur, [])

    for indicateur in indicateurs:
        if indicateur not in df_joueur.columns:
            continue

        for i in range(28, len(df_joueur)):
            semaine_a = df_joueur.iloc[i-7:i]
            semaine_c = df_joueur.iloc[i-28:i-7]
            charge_aigue = semaine_a[indicateur].sum()
            charge_chronique = semaine_c[indicateur].sum() * 0.333

            if charge_chronique == 0 or charge_aigue == 0:
                continue

            acwr = charge_aigue / charge_chronique 
            if not (acwr < 0.8 or acwr > 1.2):
                continue

            date_fin_semaine_a = semaine_a["Activity Date"].max()

            blessure_dans_15j = False
            date_blessure = pd.NA
            for blessure_date in blessures_joueur:
                if date_fin_semaine_a < blessure_date <= date_fin_semaine_a + pd.Timedelta(days=15):
                    blessure_dans_15j = True
                    date_blessure = blessure_date
                    break


            acwr_preoccupants.append({
                    "Nom de joueur": joueur,
                    "Date fin semaine A": date_fin_semaine_a,
                    "ACWR": acwr,
                    "Charge aigue": charge_aigue,
                    "Charge chronique": charge_chronique,
                    "Indicateur": indicateur,
                    "Date blessure": date_blessure,
                    "Blessure survenue" : int(blessure_dans_15j)
                })

# Création du DataFrame final
resultats_df = pd.DataFrame(acwr_preoccupants)
resultats_df = resultats_df[resultats_df["ACWR"] != 0] 

# === 3. Heatmap des indicateurs 7j avant blessure vs sans blessure ===

blessure_data = []
no_blessure_data = []

for joueur in df['Nom de joueur'].unique():
    df_joueur = df[df['Nom de joueur'] == joueur].copy().sort_values("Activity Date").reset_index(drop=True)
    blessures_joueur = blessures_dict.get(joueur, [])

    for i in range(28, len(df_joueur)):
        semaine = df_joueur.iloc[i-15:i]
        semaine_date = semaine["Activity Date"].max()
        
        if semaine[indicateurs].isnull().all().all():
            continue  # ignorer si tous les indicateurs sont NaN
        
        valeurs = semaine[indicateurs].mean()

        # Blessure dans les 15 jours ?
        is_blessure = any(semaine_date < d <= semaine_date + pd.Timedelta(days=15) for d in blessures_joueur)

        if is_blessure:
            blessure_data.append(valeurs)
        else:
            no_blessure_data.append(valeurs)

# Moyennes par groupe
moy_blessure = pd.DataFrame(blessure_data).mean()
moy_non_blessure = pd.DataFrame(no_blessure_data).mean()

# Calcul de la différence relative
comparaison = pd.DataFrame({
    "Blessure": moy_blessure,
    "Non blessure": moy_non_blessure,
    "Différence (%)": ((moy_blessure - moy_non_blessure) / moy_non_blessure * 100).round(1)
})

# Trier les indicateurs par ordre décroissant de la différence
comparaison_sorted = comparaison.sort_values(by="Différence (%)", ascending=False)

# Heatmap
plt.figure(figsize=(10, 6))
sns.heatmap(comparaison_sorted[["Différence (%)"]], annot=True, cmap="coolwarm", center=0, fmt=".1f")
plt.title("Variation des indicateurs (15j) avant blessure vs non-blessure")
plt.tight_layout()
plt.show()

# ===  Corrélation entre tranche d'âge et durée de blessure ===

# Extraire les colonnes nécessaires
df_duree = df_blessure[["Nom joueur", "Durée blessure"]]
df_age = df_info[["Nom joueur", "Age"]]

# Fusionner les infos blessure + âge
df_merged = pd.merge(df_duree, df_age, on="Nom joueur", how="left")

# Supprimer les lignes sans infos
df_merged = df_merged.dropna(subset=["Age", "Durée blessure"])

# Ajouter la tranche d'âge
df_merged["Tranche d'âge"] = df_merged["Age"].apply(get_tranche)

# Tracer un boxplot
plt.figure(figsize=(10, 6))
ordre_tranches = ["17-20", "21-24", "25-28", "29-32", "33+"]
sns.boxplot(data=df_merged, x="Tranche d'âge", y="Durée blessure", palette="Set2", order=ordre_tranches)
sns.boxplot(data=df_merged, x="Tranche d'âge", y="Durée blessure", palette="Set2")
plt.title("Durée des blessures selon la tranche d'âge")
plt.xlabel("Tranche d'âge")
plt.ylabel("Durée de blessure (jours)")
plt.grid(True)
plt.tight_layout()
plt.show()

# Calculer et afficher la corrélation linéaire
correlation = df_merged["Age"].corr(df_merged["Durée blessure"])
print(f"Corrélation entre âge et durée de blessure : {correlation:.2f}")




















strain_rows = []

# Parcours des joueurs
for joueur in df['Nom de joueur'].unique():
    df_joueur = df[df['Nom de joueur'] == joueur].copy().sort_values("Activity Date").reset_index(drop=True)
    blessures_joueur = blessures_dict.get(joueur, [])

    for i in range(7, len(df_joueur)):
        semaine = df_joueur.iloc[i-7:i]
        date_ref = semaine["Activity Date"].max()

        for indicateur in indicateurs:
            charges = semaine[indicateur]

            if charges.isnull().all():
                continue

            moyenne = charges.mean()
            ecart_type = charges.std()

            if ecart_type == 0 or pd.isna(ecart_type):
                continue

            monotony = moyenne / ecart_type
            strain = moyenne * monotony

            # Vérifie blessure dans les 15 jours
            blessure_dans_15j_monotony = False
            date_blessure_monotony = pd.NA
            for b in blessures_joueur:
                if date_ref < b <= date_ref + pd.Timedelta(days=15):
                    date_blessure_monotony = b
                    blessure_dans_15j_monotony = True
                    break

            # Condition stricte
            if ((monotony < 1 or monotony > 2) and strain > 6000):
                strain_rows.append({
                    "Nom joueur": joueur,
                    "Date de référence": date_ref,
                    "Nom indicateur": indicateur,
                    "Monotony": round(monotony, 2),
                    "Strain": round(strain, 2),
                    "Blessure dans 15j": int(blessure_dans_15j_monotony),
                    "Date blessure": date_blessure_monotony,
                })

# Créer le DataFrame final
strain_df = pd.DataFrame(strain_rows)


# Catégorisation de l'ACWR
def categoriser_acwr(val):
    if val < 0.8:
        return "<0.8"
    elif 0.8 <= val <= 1.2:
        return "0.8–1.2"
    elif 1.2 < val <= 1.5:
        return "1.2–1.5"
    else:
        return ">1.5"

resultats_df["Catégorie ACWR"] = resultats_df["ACWR"].apply(categoriser_acwr)

# Calcul du pourcentage de blessés par catégorie
acwr_stats = resultats_df.groupby("Catégorie ACWR")["Blessure survenue"].agg(
    total_cas="count",
    nb_blessures="sum"
).reset_index()

acwr_stats["Pourcentage de blessés"] = round((acwr_stats["nb_blessures"] / acwr_stats["total_cas"]) * 100, 1)

print(acwr_stats)

# Style de graphique
sns.set(style="whitegrid")

# Création du graphique
plt.figure(figsize=(8, 6))
palette = sns.color_palette("Reds", len(acwr_stats))  # palette rouge pour les risques

barplot = sns.barplot(
    data=acwr_stats.sort_values("Catégorie ACWR"),
    x="Catégorie ACWR",
    y="Pourcentage de blessés",
    palette=palette
)

# Affichage des pourcentages au-dessus des barres
for index, row in acwr_stats.iterrows():
    barplot.text(
        index, 
        row["Pourcentage de blessés"] + 1, 
        f"{row['Pourcentage de blessés']}%", 
        color='black', 
        ha="center"
    )

# Titres et labels
plt.title("Pourcentage de blessures selon la catégorie d’ACWR")
plt.xlabel("Catégorie d’ACWR")
plt.ylabel("Pourcentage de blessures (%)")
plt.ylim(0, acwr_stats["Pourcentage de blessés"].max() + 10)

plt.tight_layout()
plt.show()



plt.figure(figsize=(10, 6))
sns.boxplot(
    data=resultats_df,
    x="Blessure survenue",  # 0 = non blessé, 1 = blessé dans les 15 jours
    y="ACWR",
    palette="Set2"
)

# Limite de l’axe Y
plt.ylim(0, 3)

# Personnalisation
plt.title("Distribution de l'ACWR chez les blessés vs non blessés")
plt.xlabel("Blessure dans les 15 jours (0 = non, 1 = oui)")
plt.ylabel("ACWR")
plt.grid(True)
plt.tight_layout()

plt.show()







plt.figure(figsize=(10, 6))
sns.boxplot(data=strain_df, x="Blessure dans 15j", y="Strain", palette="Set2")
plt.title("Distribution du Strain chez les blessés vs non blessés")
plt.xlabel("Blessure dans les 15 jours (0 = non, 1 = oui)")
plt.ylabel("Strain")
plt.grid(True)
plt.ylim(0, 50000)
plt.tight_layout()
plt.show()










# Nouveau calcul combiné ACWR + Strain + blessure
conditions_preoccupantes = []

for joueur in df['Nom de joueur'].unique():
    df_joueur = df[df['Nom de joueur'] == joueur].copy().sort_values("Activity Date").reset_index(drop=True)
    blessures_joueur = blessures_dict.get(joueur, [])

    for i in range(28, len(df_joueur)):
        semaine_7j = df_joueur.iloc[i-7:i]
        semaine_21j = df_joueur.iloc[i-28:i-7]
        date_ref = semaine_7j["Activity Date"].max()

        for indicateur in indicateurs:
            charges_7j = semaine_7j[indicateur]
            charges_21j = semaine_21j[indicateur]

            if charges_7j.isnull().all() or charges_21j.isnull().all():
                continue

            # === Calcul ACWR ===
            charge_aigue = charges_7j.sum()
            charge_chronique = charges_21j.sum() * 0.333  # moyenne sur 3 semaines

            if charge_chronique == 0 or charge_aigue == 0:
                continue

            acwr = charge_aigue / charge_chronique

            # === Calcul Strain ===
            moyenne_7j = charges_7j.mean()
            ecart_type_7j = charges_7j.std()

            if ecart_type_7j == 0 or pd.isna(ecart_type_7j):
                continue

            monotony = moyenne_7j / ecart_type_7j
            strain = moyenne_7j * monotony

            # === Blessure dans les 15j ===
            blessure_dans_15j = False
            date_blessure = pd.NA
            for b in blessures_joueur:
                if date_ref < b <= date_ref + pd.Timedelta(days=15):
                    blessure_dans_15j = True
                    date_blessure = b
                    break

            # === Conditions préoccupantes ===
            if (monotony > 0.3 or monotony < 0.1) and (acwr > 1.3 or acwr < 0.3):
                conditions_preoccupantes.append({
                    "Nom joueur": joueur,
                    "Date de référence": date_ref,
                    "Indicateur": indicateur,
                    "Monotony" : round(monotony, 2),
                    "ACWR": round(acwr, 2),
                    "Strain": round(strain, 2),
                    "Blessure dans 15j": int(blessure_dans_15j),
                    "Date blessure": date_blessure
                })

# Création du DataFrame final
df_conditions_preoccupantes = pd.DataFrame(conditions_preoccupantes)


# Calcul du pourcentage de blessures parmi les cas préoccupants
nb_total = len(df_conditions_preoccupantes)
nb_blessures = df_conditions_preoccupantes["Blessure dans 15j"].sum()
pourcentage_blessures = round((nb_blessures / nb_total) * 100, 1) if nb_total > 0 else 0

print(f"📊 Pourcentage de blessures parmi les cas préoccupants : {pourcentage_blessures}% ({nb_blessures}/{nb_total})")








indicateurs_2 = [ 
    "Distance (m)", 
    "Distance HID (>15 km/h)", 
    "Distance HID (>20 km/h)",
]

comparaisons = []
seuil_alerte = 30  # seuil d'écart en %

for _, row in df_blessure.iterrows():
    joueur = row["Nom joueur"]
    date_blessure = row["Début blessure"]

    if pd.isna(date_blessure) or joueur not in df['Nom de joueur'].unique():
        continue

    date_debut_analyse = date_blessure - pd.Timedelta(days=15)

    df_joueur = df[(df["Nom de joueur"] == joueur) &
                   (df["Activity Date"] >= date_debut_analyse) &
                   (df["Activity Date"] < date_blessure)]

    df_autres = df[(df["Nom de joueur"] != joueur) &
                   (df["Activity Date"] >= date_debut_analyse) &
                   (df["Activity Date"] < date_blessure)]

    ligne = {
        "Nom joueur": joueur,
        "Date blessure": date_blessure
    }

    for indicateur in indicateurs_2:
        if indicateur not in df.columns:
            continue

        somme_joueur = df_joueur[indicateur].sum()
        somme_autres = df_autres.groupby("Nom de joueur")[indicateur].sum().mean()

        ecart_pct = np.nan
        if pd.notna(somme_joueur) and pd.notna(somme_autres) and somme_autres != 0:
            ecart_pct = ((somme_joueur - somme_autres) / somme_autres) * 100

        ligne[f"{indicateur} - joueur blessé"] = somme_joueur
        ligne[f"{indicateur} - moyenne autres"] = somme_autres
        ligne[f"{indicateur} - écart %"] = round(ecart_pct, 1) if pd.notna(ecart_pct) else np.nan
        ligne[f"{indicateur} - alerte"] = abs(ecart_pct) >= seuil_alerte if pd.notna(ecart_pct) else False

    comparaisons.append(ligne)

# DataFrame final
comparaison_blessure_15j = pd.DataFrame(comparaisons)



# Extraire toutes les colonnes d'écart %
colonnes_ecarts = [col for col in comparaison_blessure_15j.columns if col.endswith("- écart %")]

# Convertir en une seule série pour tout concaténer
ecarts_total = comparaison_blessure_15j[colonnes_ecarts].values.flatten()

# Nettoyer les valeurs manquantes
ecarts_total_clean = ecarts_total[~pd.isna(ecarts_total)]

# Calcul de la moyenne des écarts
moyenne_ecart_global = np.mean(ecarts_total_clean)

print(f"📊 Moyenne globale de l'écart (%) entre les joueurs blessés et le groupe (sur 15j avant blessure) : {moyenne_ecart_global:.2f}%")

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
plt.show()




# Ajouter l'âge à df_blessure
df_blessure_age = df_blessure.merge(df_info[['Nom joueur', 'Age']], on="Nom joueur", how="left")

# Ajouter la tranche d'âge
df_blessure_age["Tranche d'âge"] = df_blessure_age["Age"].apply(get_tranche)

# Nombre de blessures par tranche
blessures_par_tranche = df_blessure_age["Tranche d'âge"].value_counts().sort_index()

# Nombre de joueurs par tranche pour normaliser (fréquence relative)
joueurs_par_tranche = df_info["Age"].apply(get_tranche).value_counts().sort_index()

# Fréquence de blessure = nb blessures / nb joueurs dans la tranche
freq_blessure_par_tranche = (blessures_par_tranche / joueurs_par_tranche).dropna().sort_index()

# Préparation pour la corrélation
# On doit transformer les tranches d'âge en valeurs numériques
tranche_to_num = {"17-20": 1, "21-24": 2, "25-28": 3, "29-32": 4, "33+": 5}
x = [tranche_to_num[tranche] for tranche in freq_blessure_par_tranche.index]
y = freq_blessure_par_tranche.values

# Calcul de la corrélation
correlation = np.corrcoef(x, y)[0, 1]

print(f"📈 Corrélation entre tranche d’âge et fréquence des blessures : {correlation:.2f}")

# Affichage graphique
plt.figure(figsize=(8, 5))
sns.barplot(x=list(freq_blessure_par_tranche.index), y=freq_blessure_par_tranche.values, palette="Set2")
plt.title("Fréquence des blessures par tranche d'âge (normalisée par nombre de joueurs)")
plt.xlabel("Tranche d'âge")
plt.ylabel("Fréquence des blessures")
plt.grid(True)
plt.tight_layout()
plt.show()




































































