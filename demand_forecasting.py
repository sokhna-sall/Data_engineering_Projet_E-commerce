"""
Fichier : demand_forecasting.py
Description : Composant IA du pipeline. Entraîne un modèle de régression (Random Forest)
              sur les données Gold pour prédire la demande à J+7.
"""

import os
from xml.parsers.expat import model
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta

# Configuration des chemins
GOLD_PARQUET = "data/gold/gold_fact_daily_demand.parquet"
PREDICTIONS_OUTPUT = "data/gold/predictions_demand_j7.parquet"

def train_and_forecast():
    print("=== [MACHINE LEARNING] Début de la phase de modélisation prédictive ===")
    
    if not os.path.exists(GOLD_PARQUET):
        raise FileNotFoundError(f"Impossible de trouver la table Gold à l'emplacement : {GOLD_PARQUET}")
        
    # 1. Chargement des données historiques Gold
    df = pd.read_parquet(GOLD_PARQUET)
    
    # 2. Préparation des variables (Features) et de la cible (Target)
    # Nous prédisons les quantités vendues à partir de la navigation et des tendances externes
    features = ['total_visites', 'total_ajouts_panier', 'indice_popularite_web']
    target = 'quantite_vendue_totale'
    
    X = df[features]
    y = df[target]
    
    print(f"[ML INFO] Entraînement du modèle sur {len(df)} lignes historiques...")
    
    # 3. Initialisation et entraînement de l'algorithme Random Forest
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # R2 Score indicatif sur le set d'entraînement
    score_r2 = model.score(X, y)
    print(f"[ML SUCCESS] Modèle entraîné. Score R² de performance : {score_r2:.4f}")
    
    # 4. Simulation et génération des prévisions pour les 7 prochains jours (J+1 à J+7)
    print("[ML] Calcul des projections de demande à J+7 (8 Juillet au 14 Juillet 2026)...")
    
    derniere_date = pd.to_datetime(df['date_reference']).max()
    liste_produits = df[['product_id', 'product_name', 'category', 'unit_price']].drop_duplicates().to_dict('records')
    
    records_previsions = []
    
    # Pour chaque produit et pour chaque jour futur, on projette la demande
    for p in liste_produits:
        # On récupère les moyennes récentes du produit pour simuler l'état futur des features
        stats_recents = df[df['product_id'] == p['product_id']][features].mean().values
        
        # Si le produit n'a pas d'historique de clics, on applique des valeurs par défaut
        if np.isnan(stats_recents).any():
            stats_recents = [20, 5, 50]
            
        for day_offset in range(1, 8):
            date_future = derniere_date + timedelta(days=day_offset)
            
            # Injection d'un léger bruit aléatoire pour simuler la fluctuation réelle du marché
            # 1. Génération du facteur aléatoire
            random_factor = np.random.uniform(0.85, 1.15, size=3)
            
            # 2. Calcul des features simulées
            features_simulees = stats_recents * random_factor
            
            # Inférence / Prédiction de la quantité requise
            features_df = pd.DataFrame([features_simulees], columns=features)
            prediction_quantite = model.predict(features_df)[0]
            quantite_arrondie = max(0, int(np.ceil(prediction_quantite))) # Pas de quantité négative, arrondi supérieur
            
            records_previsions.append({
                "date_reference": date_future.strftime("%Y-%m-%d"),
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "category": p["category"],
                "unit_price": float(p["unit_price"]),
                "demande_predite": quantite_arrondie,
                "stock_securite_recommande": int(np.ceil(quantite_arrondie * 1.5)) # Règle métier : +50% de marge de sécurité
            })
            
    # 5. Sauvegarde des résultats au format Parquet pour le Dashboard
    df_forecast = pd.DataFrame(records_previsions)
    df_forecast.to_parquet(PREDICTIONS_OUTPUT, index=False)
    print(f"[ML DONE] Fichier de prévisions matérialisé : {PREDICTIONS_OUTPUT} ({len(df_forecast)} lignes)")

if __name__ == "__main__":
    train_and_forecast()