"""
Fichier : transform_pipeline.py
Description : Pipeline ELT Modern Data Stack utilisant DuckDB pour le nettoyage (Silver),
              la validation de la qualité et l'agrégation binaire Parquet (Gold).
"""

import os
import duckdb

# 1. Définition des constantes de chemins (Architecture en Médaillon)
BRONZE_DIR = "data/bronze"
SILVER_DIR = "data/silver"
GOLD_DIR = "data/gold"
DB_PATH = "data/ecommerce_analytics.db"

def init_environment():
    """Crée les dossiers applicatifs si nécessaires."""
    os.makedirs(SILVER_DIR, exist_ok=True)
    os.makedirs(GOLD_DIR, exist_ok=True)

def run_bronze_to_silver():
    """
    Étape 1 : Ingestion de Bronze et Transformation vers Silver.
    Nettoie les anomalies de casse, gère les valeurs aberrantes et normalise les dates.
    """
    print("=== [COUCHE SILVER] Début de la phase de nettoyage et conformité ===")
    init_environment()
    
    # Initialisation de la connexion persistante locale DuckDB
    con = duckdb.connect(database=DB_PATH)
    
    # --- A. Transformation du Catalogue Produits ---
    print("[SILVER] Traitement du catalogue produits...")
    con.execute("DROP TABLE IF EXISTS silver_catalogue")
    con.execute(f"""
        CREATE TABLE silver_catalogue AS
        SELECT 
            "Produit ID" AS product_id,
            -- Remplacement de INITCAP(TRIM(...)) par une manipulation robuste :
            -- Met la première lettre en majuscule et le reste en minuscule
            UPPER(LEFT(TRIM("Nom du produit"), 1)) || LOWER(SUBSTRING(TRIM("Nom du produit"), 2)) AS product_name,
            "Catégorie" AS category,
            CAST(Prix AS DECIMAL(10,2)) AS price
        FROM read_csv_auto('{BRONZE_DIR}/catalogue_produits.csv')
    """)
    # --- B. Transformation de l'Historique des Ventes ---
    print("[SILVER] Traitement de l'historique des ventes...")
    con.execute("DROP TABLE IF EXISTS silver_ventes")
    con.execute(f"""
        CREATE TABLE silver_ventes AS
        SELECT 
            "Identifiant Commande" AS order_id,
            CAST("Date de vente" AS TIMESTAMP) AS sale_date,
            "Produit ID" AS product_id,
            CAST("Quantité vendue" AS INTEGER) AS quantity,
            TRY_CAST("Montant de la vente" AS DECIMAL(10,2)) AS amount
        FROM read_csv_auto('{BRONZE_DIR}/historique_ventes.csv')
        -- Utilisation de TRY_CAST pour éviter l'erreur de conversion
        -- On ne garde que les lignes où le montant est bien un nombre valide et supérieur à 0
        WHERE TRY_CAST("Montant de la vente" AS DECIMAL(10,2)) IS NOT NULL
          AND TRY_CAST("Montant de la vente" AS DECIMAL(10,2)) > 0
    """)
    
    # --- C. Transformation des Tendances Externes (Gestion de la date hybride) ---
    print("[SILVER] Traitement des tendances exogènes...")
    con.execute("DROP TABLE IF EXISTS silver_tendances")
    con.execute(f"""
        CREATE TABLE silver_tendances AS
        SELECT 
            "Mot-clé ou tendance" AS keyword,
            CAST("Indice de popularité" AS INTEGER) AS popularity_index,
            cat_associee AS associated_category,
            -- Règle SQL conditionnelle pour traiter le format hybride (Texte ISO vs Timestamp Unix)
            CASE 
                WHEN TRY_CAST("Date de collecte" AS BIGINT) IS NOT NULL 
                THEN CAST(TO_TIMESTAMP(CAST("Date de collecte" AS BIGINT)) AS DATE)
                ELSE CAST("Date de collecte" AS DATE)
            END AS collection_date
        FROM read_json_auto('{BRONZE_DIR}/tendances_externes.json')
    """)
    
    # --- D. Transformation du Clickstream JSON (Aplatissement) ---
    print("[SILVER] Aplatissement du flux clickstream...")
    con.execute("DROP TABLE IF EXISTS silver_clickstream")
    con.execute(f"""
        CREATE TABLE silver_clickstream AS
        SELECT 
            "Session ID" AS session_id,
            CAST("Date/Heure de clic" AS TIMESTAMP) AS click_timestamp,
            "Page visitée / Action" AS action_type,
            Utilisateur AS user_id, -- Donnée sensible (Pseudonymisation possible ici)
            prod_concerne AS product_id
        FROM read_json_auto('{BRONZE_DIR}/clickstream.json')
    """)
    
    con.close()
    print("[SILVER] Étape Bronze -> Silver terminée avec succès.")

def run_data_quality_tests():
    """
    Étape 2 : Data Quality Gate (Bloquant).
    Exécute des assertions sur la couche Silver. Lève une exception en cas de non-conformité.
    """
    print("=== [DATA QUALITY] Exécution des vérifications de conformité ===")
    con = duckdb.connect(database=DB_PATH)
    
    # Test 1 : Vérification de l'absence totale de montants NULL ou non définis
    null_count = con.execute("SELECT COUNT(*) FROM silver_ventes WHERE amount IS NULL").fetchone()[0]
    
    # Test 2 : Vérification de la cohérence financière (Pas de transactions négatives ou nulles)
    negative_count = con.execute("SELECT COUNT(*) FROM silver_ventes WHERE amount <= 0").fetchone()[0]
    
    con.close()
    
    print(f"[QUALITY CHECKS] Analyse effectuée : {null_count} NULL détecté(s), {negative_count} montant(s) négatif(s).")
    
    # Condition d'arrêt critique du pipeline (Coupe-circuit)
    if null_count > 0 or negative_count > 0:
        raise ValueError(
            f"[CRITICAL FAIL] Qualité des données insuffisante ! "
            f"Pipeline stoppé. Détails : {null_count} NULLs, {negative_count} montants aberrants."
        )
    
    print("[QUALITY PASS] Toutes les assertions de qualité sont au statut : VALIDE.")

def run_silver_to_gold():
    """
    Étape 3 : Transformation de Silver vers Gold (Modélisation Dimensionnelle).
    Agrége les données à la granularité Jour/Produit et exporte au format binaire Parquet.
    """
    print("=== [COUCHE GOLD] Début de la phase d'agrégation décisionnelle ===")
    con = duckdb.connect(database=DB_PATH)
    
    # Requête d'agrégation et de jointure multidimensionnelle (Ventes, Clickstream et Tendances)
    gold_query = """
        WITH v_daily AS (
            SELECT 
                CAST(sale_date AS DATE) AS ref_date,
                product_id,
                SUM(quantity) AS total_quantity_sold,
                SUM(amount) AS total_revenue
            FROM silver_ventes
            GROUP BY 1, 2
        ),
        c_daily AS (
            SELECT 
                CAST(click_timestamp AS DATE) AS ref_date,
                product_id,
                COUNT(CASE WHEN action_type = 'visite produit' THEN 1 END) AS total_product_views,
                COUNT(CASE WHEN action_type = 'ajout au panier' THEN 1 END) AS total_cart_additions
            FROM silver_clickstream
            GROUP BY 1, 2
        )
        SELECT 
            COALESCE(v.ref_date, c.ref_date) AS date_reference,
            p.product_id,
            p.product_name,
            p.category,
            p.price AS unit_price,
            COALESCE(v.total_quantity_sold, 0) AS quantite_vendue_totale,
            COALESCE(v.total_revenue, 0.0) AS chiffre_affaires,
            COALESCE(c.total_product_views, 0) AS total_visites,
            COALESCE(c.total_cart_additions, 0) AS total_ajouts_panier,
            COALESCE(t.popularity_index, 50) AS indice_popularite_web
        FROM silver_catalogue p
        LEFT JOIN v_daily v ON p.product_id = v.product_id
        LEFT JOIN c_daily c ON p.product_id = c.product_id AND COALESCE(v.ref_date, c.ref_date) = c.ref_date
        LEFT JOIN silver_tendances t ON p.category = t.associated_category 
            AND t.collection_date = COALESCE(v.ref_date, c.ref_date)
        WHERE COALESCE(v.ref_date, c.ref_date) IS NOT NULL
        ORDER BY date_reference DESC, product_id ASC
    """
    
    gold_parquet_path = os.path.join(GOLD_DIR, "gold_fact_daily_demand.parquet")
    
    # Export direct au format hautement performant Apache Parquet (Écrase le fichier précédent)
    con.execute(f"COPY ({gold_query}) TO '{gold_parquet_path}' (FORMAT PARQUET)")
    
    # Métrique de log pour Airflow
    total_rows = con.execute(f"SELECT COUNT(*) FROM '{gold_parquet_path}'").fetchone()[0]
    con.close()
    
    print(f"[GOLD SUCCESS] Matrice Gold générée avec succès : {gold_parquet_path}")
    print(f"[GOLD INFO] Volume final de la table : {total_rows} lignes prêtes pour le Machine Learning.")

if __name__ == "__main__":
    # Bloc d'exécution locale pour tests unitaires hors Airflow
    print("--- DÉMARRAGE DU PIPELINE EN MODE AUTONOME / TEST ---")
    try:
        run_bronze_to_silver()
        run_data_quality_tests()
        run_silver_to_gold()
        print("--- PIPELINE EXÉCUTÉ SANS ERREUR EN LOCAL ---")
    except Exception as e:
        print(f"Erreur lors de l'exécution : {e}")