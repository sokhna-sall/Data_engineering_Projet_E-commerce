"""
Fichier : generate_mock_data.py
Description : Script de génération de données e-commerce fictives (Couche Bronze)
              avec injection volontaire d'anomalies pour valider le pipeline ELT.
Institution : École Polytechnique de Thiès (EPT)
"""

import os
import csv
import json
import random
from datetime import datetime, timedelta

# Configurations des répertoires
OUTPUT_DIR = "data/bronze"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Fixer la graine aléatoire pour garantir le déterminisme des anomalies
random.seed(42)

# 1. Génération du Référentiel Catalogue Produits
categories = ["Électronique", "Mode", "Maison", "Sport", "Livres"]
noms_par_cat = {
    "Électronique": ["Ecran Pro", "SMARTPHONE MAX", "souris eco", "Casque Audio"],
    "Mode": ["Veste Cuir", "ROBE CLASSIQUE", "jean slim", "Chaussures Sport"],
    "Maison": ["Lampe LED", "Chaise Bureau", "TAPIS SALON", "Cafetière Pro"],
    "Sport": ["Gourde Inox", "TAPIS DE COURSE", "haltere eco", "Sac Dos"],
    "Livres": ["Roman Poche", "BD AVENTURE", "manuel math", "Guide Voyage"]
}

produits = []
for i in range(1, 21):
    p_id = f"PROD_{i:03d}"
    cat = random.choice(categories)
    # Simulation des anomalies de casse (MAJUSCULES / minuscules)
    nom_brut = random.choice(noms_par_cat[cat])
    if i % 3 == 0:
        nom_brut = nom_brut.upper()
    elif i % 5 == 0:
        nom_brut = nom_brut.lower()
        
    prix = round(random.uniform(10.0, 500.0), 2)
    produits.append({"id": p_id, "nom": nom_brut, "categorie": cat, "prix": prix})

catalog_path = os.path.join(OUTPUT_DIR, "catalogue_produits.csv")
with open(catalog_path, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Produit ID", "Nom du produit", "Catégorie", "Prix"])
    for p in produits:
        writer.writerow([p["id"], p["nom"], p["categorie"], p["prix"]])

print(f"[OK] Fichier créé : {catalog_path} ({len(produits)} produits)")


# 2. Génération des Ventes, Clickstream et Tendances (Historique sur 30 jours)
start_date = datetime(2026, 6, 7)
ventes_rows = []
clickstream_data = []
tendances_data = []

cmd_counter = 5000
session_counter = 1000

# Génération des tendances journalières
mots_cles = {
    "Électronique": "soldes informatique",
    "Mode": "look été",
    "Maison": "deco design",
    "Sport": "fitness home",
    "Livres": "lecture vacances"
}

for day_offset in range(30):
    current_date = start_date + timedelta(days=day_offset)
    date_str_iso = current_date.strftime("%Y-%m-%d")
    
    # Génération des tendances (JSON)
    for cat, keyword in mots_cles.items():
        popularity = random.randint(30, 95)
        # Injection de l'anomalie de format de date hybride (Timestamp Unix)
        if day_offset % 7 == 0:
            date_field = int(current_date.timestamp())
        else:
            date_field = date_str_iso
            
        tendances_data.append({
            "Mot-clé ou tendance": keyword,
            "Indice de popularité": popularity,
            "Date de collecte": date_field,
            "cat_associee": cat
        })

    # Génération des transactions et parcours utilisateurs
    for _ in range(15):  # 15 sessions par jour
        cmd_counter += 1
        session_counter += 1
        sess_id = f"SESS_{session_counter:08X}"
        user_id = f"USER_{random.randint(10, 99):04d}"
        prod = random.choice(produits)
        
        h_base = current_date + timedelta(hours=random.randint(8, 20), minutes=random.randint(0, 59))
        
        # Clickstream : Événement 1 - Visite
        clickstream_data.append({
            "Session ID": sess_id,
            "Date/Heure de clic": h_base.strftime("%Y-%m-%dT%H:%M:%S"),
            "Page visitée / Action": "visite produit",
            "Utilisateur": user_id,
            "prod_concerne": prod["id"]
        })
        
        # Clickstream : Événement 2 - Ajout au panier (80% des cas)
        if random.random() > 0.2:
            h_cart = h_base + timedelta(minutes=random.randint(1, 10))
            clickstream_data.append({
                "Session ID": sess_id,
                "Date/Heure de clic": h_cart.strftime("%Y-%m-%dT%H:%M:%S"),
                "Page visitée / Action": "ajout au panier",
                "Utilisateur": user_id,
                "prod_concerne": prod["id"]
            })
            
            # Transaction : Achat finalisé (50% des ajouts au panier)
            if random.random() > 0.5:
                h_buy = h_cart + timedelta(minutes=random.randint(1, 5))
                quantite = random.randint(1, 4)
                montant_theorique = round(quantite * prod["prix"], 2)
                
                # Injection déterministe d'anomalies sur le montant des ventes
                if cmd_counter % 25 == 0:
                    montant_final = ""  # Anomalie : Valeur manquante (Chaîne vide)
                elif cmd_counter % 40 == 0:
                    montant_final = f"-{montant_theorique}"  # Anomalie : Montant négatif
                else:
                    montant_final = str(montant_theorique)
                    
                ventes_rows.append([
                    f"CMD_{cmd_counter}",
                    h_buy.strftime("%Y-%m-%dT%H:%M:%S"),
                    prod["id"],
                    quantite,
                    montant_final
                ])

# Écriture de l'historique des ventes (CSV)
ventes_path = os.path.join(OUTPUT_DIR, "historique_ventes.csv")
with open(ventes_path, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Identifiant Commande", "Date de vente", "Produit ID", "Quantité vendue", "Montant de la vente"])
    writer.writerows(ventes_rows)

print(f"[OK] Fichier créé : {ventes_path} ({len(ventes_rows)} lignes de ventes)")

# Écriture du clickstream (JSON)
clickstream_path = os.path.join(OUTPUT_DIR, "clickstream.json")
with open(clickstream_path, mode='w', encoding='utf-8') as f:
    json.dump(clickstream_data, f, indent=4, ensure_ascii=False)

print(f"[OK] Fichier créé : {clickstream_path} ({len(clickstream_data)} clics)")

# Écriture des tendances externes (JSON)
tendances_path = os.path.join(OUTPUT_DIR, "tendances_externes.json")
with open(tendances_path, mode='w', encoding='utf-8') as f:
    json.dump(tendances_data, f, indent=4, ensure_ascii=False)

print(f"[OK] Fichier créé : {tendances_path} ({len(tendances_data)} enregistrements de tendances)")
print("\n=== COUCHE BRONZE MATÉRIALISÉE AVEC ANOMALIES SÉCURISÉES ===")