import csv
import uuid
import os
import shutil
import glob # Added for glob.glob in summary
from datetime import datetime
from collections import defaultdict, Counter
from tabulate import tabulate
import zipfile # Added for ZIP creation

# === Config ===
# NOTE: These paths MUST be valid on the machine running the script.
SOURCE_CSV_PATHS = {
    "others": "source_data/others-test-package.csv",
    "warnerbros": "source_data/warnerbros-test-package.csv"
}
SOURCE_MEDIA_DIR = "source_data/media"
OUTPUT_DIR = os.path.join(os.getcwd(), "GENERATED_PACKAGES") # Changed OUTPUT_DIR to a subdir for cleaner zipping
LANDSCAPE_IMAGE = "encode-aes2805-2-16x9.jpg"
PORTRAIT_IMAGE = "encode-aes2805-1-2x3.jpg"
VIDEO_FILE = "encode-aes2805-2.mp4"

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Utility Functions (Unmodified) ===

def random_id(n):
    return uuid.uuid4().hex[-n:]

def generate_common_names(prefix):
    date_str = datetime.today().strftime('%d-%m-%y')
    uid4 = random_id(4)
    uid6 = random_id(6)
    return {
        "title": f"Test-Mops-{prefix}-{date_str}-{uid4}",
        "short_desc": f"Description of Test-Mops-{prefix}-{date_str}-{uid4}",
        "long_desc": f"Short Description of Test-Mops-{prefix}-{date_str}-{uid4}",
        "video": f"mops-test-{prefix.lower()}-{uid6}.mp4",
        "landscape": f"mops-test-{prefix.lower()}-16x9-{uid6}.jpg",
        "portrait": f"mops-test-{prefix.lower()}-2x3-{uid6}.jpg",
        "package_id": str(uuid.uuid4())
    }

def copy_assets(destination_folder, names):
    shutil.copyfile(os.path.join(SOURCE_MEDIA_DIR, VIDEO_FILE), os.path.join(destination_folder, names["video"]))
    shutil.copyfile(os.path.join(SOURCE_MEDIA_DIR, LANDSCAPE_IMAGE), os.path.join(destination_folder, names["landscape"]))
    shutil.copyfile(os.path.join(SOURCE_MEDIA_DIR, PORTRAIT_IMAGE), os.path.join(destination_folder, names["portrait"]))

def load_csv_rows(provider):
    path = SOURCE_CSV_PATHS[provider]
    with open(path, newline='', encoding='utf-8') as csvfile:
        return list(csv.DictReader(csvfile))

def save_csv(provider, rows, headers):
    folder = os.path.join(OUTPUT_DIR, provider)
    os.makedirs(folder, exist_ok=True)
    uid4 = uuid.uuid4().hex[-4:]
    csv_path = os.path.join(folder, f"generated-{provider}-test-package-{uid4}.csv")
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            trimmed_row = {k: v for k, v in row.items() if k in headers}
            writer.writerow(trimmed_row)
    return csv_path

# === Core Logic Functions (Modified for Flask) ===

def run_generation(mode, manual_configs=None):
    """
    Runs the test package generation based on the selected mode and configuration.

    Args:
        mode (str): 'default' or 'manual'.
        manual_configs (dict): The configuration from the web form for manual mode.

    Returns:
        tuple: (zip_path, message) where zip_path is the path to the created zip,
               or None if an error occurred.
    """
    
    # Define all available providers and products for default mode setup
    all_providers = list(SOURCE_CSV_PATHS.keys())
    provider_products = {
        "others": ["localnow", "twc", "hbcugo"],
        "warnerbros": ["localnow"]
    }
    
    config = {}
    
    # 1. Configuration Setup
    if mode == "default":
        # Use hardcoded list
        providers = all_providers
        for provider in providers:
            for product in provider_products[provider]:
                config[f"full_movie_{provider}_{product}"] = 1
                config[f"full_episode_{provider}_{product}"] = 1
                if provider == "others" and product == "twc":
                    config[f"short_video_{provider}_{product}"] = 1
    
    elif mode == "manual":
        if not manual_configs:
             return None, "Manual configuration data is missing."
             
        # Use providers from the manual_configs keys
        providers = list(manual_configs.keys())
        provider_products = {p: list(manual_configs[p].keys()) for p in providers}

        for provider in providers:
            for product in provider_products[provider]:
                product_data = manual_configs.get(provider, {}).get(product, {})
                
                # Full Movie and Full Episode
                for vtype_raw in ["full_movie", "full_episode"]:
                    count_key = f"{vtype_raw}_{provider}_{product}"
                    count = int(product_data.get(vtype_raw, 0))
                    config[count_key] = count
                
                # Short Video (Specific to others/twc)
                if provider == "others" and product == "twc":
                    count_key = f"short_video_{provider}_{product}"
                    count = int(product_data.get('short_video', 0))
                    config[count_key] = count
    else:
        return None, "Invalid generation mode specified."

    # 2. Package Generation Loop
    all_generated_folders = []

    for provider in providers:
        try:
            src_rows = load_csv_rows(provider)
        except FileNotFoundError:
            print(f"Error: Source CSV not found for {provider}. Skipping.")
            continue
            
        if not src_rows:
            print(f"Error: Source CSV is empty for {provider}. Skipping.")
            continue
            
        headers = list(src_rows[0].keys())
        output_rows = []
        folder = os.path.join(OUTPUT_DIR, provider)
        os.makedirs(folder, exist_ok=True)
        all_generated_folders.append(folder)
        
        # Keep track of generated assets for episodes to ensure assets are only copied once per series/season
        series_meta = {} 

        for product in provider_products[provider]:
            for vtype in ["Full Movie", "Full Episode", "Short Video"]:
                
                if vtype == "Short Video" and (provider != "others" or product != "twc"):
                    continue

                count_key = f"{vtype.lower().replace(' ', '_')}_{provider}_{product}"
                count = config.get(count_key, 0)
                
                if count == 0:
                    continue

                template_row = next(
                    (r for r in src_rows if r["Video Type"].strip().lower() == vtype.lower()),
                    None
                )
                if not template_row:
                    print(f"No template row for {vtype} in {provider}")
                    continue

                if vtype == "Full Episode":
                    series_key = f"{provider}_{product}"
                    if series_key not in series_meta:
                        series_meta[series_key] = generate_common_names("Series")
                        series_meta[series_key]['season_title'] = f"Test-Mops-Season-{datetime.today().strftime('%d-%m-%y')}-{random_id(4)}"
                        series_meta[series_key]['season_desc'] = f"Description of {series_meta[series_key]['season_title']}"
                        
                        series_uid4 = random_id(4)
                        series_meta[series_key]['series_poster'] = f"test-mops-series-2x3-{series_uid4}.jpg"
                        series_meta[series_key]['series_landscape'] = f"test-mops-series-16x9-{series_uid4}.jpg"
                        series_meta[series_key]['season_landscape'] = f"test-mops-season-16x9-{series_uid4}.jpg"
                        
                        # Copy series/season assets once
                        shutil.copyfile(os.path.join(SOURCE_MEDIA_DIR, PORTRAIT_IMAGE), os.path.join(folder, series_meta[series_key]['series_poster']))
                        shutil.copyfile(os.path.join(SOURCE_MEDIA_DIR, LANDSCAPE_IMAGE), os.path.join(folder, series_meta[series_key]['series_landscape']))
                        shutil.copyfile(os.path.join(SOURCE_MEDIA_DIR, LANDSCAPE_IMAGE), os.path.join(folder, series_meta[series_key]['season_landscape']))
                    
                    meta = series_meta[series_key]
                else:
                    meta = None # Not used for Movie/Short Video

                for i in range(count):
                    row = template_row.copy()
                    names = generate_common_names("Episode" if vtype == "Full Episode" else ("Movie" if vtype == "Full Movie" else "Short"))
                    
                    # Common fields
                    row["Movie / Episode Title"] = names["title"]
                    row["Movie / Episode Short Description"] = names["short_desc"]
                    row["Movie / Episode Description"] = names["long_desc"]
                    row["Programming Type"] = vtype
                    row["Movie/Episode Video File Name (including extension)"] = names["video"]
                    row["Movie / Episode Landscape Image Name (including extension)"] = names["landscape"]
                    row["Movie Poster Image Name (including extension)"] = names["portrait"]
                    if "package_id" in row:
                        row["package_id"] = names["package_id"]
                    if "products" in row:
                        row["products"] = product
                    
                    copy_assets(folder, names)

                    if vtype == "Full Episode":
                        row["Series Title"] = meta["title"]
                        row["Series Description"] = meta["short_desc"]
                        row["Season Number"] = "1"
                        row["Season Title"] = meta["season_title"]
                        row["Season Description"] = meta["season_desc"]
                        row["Episode Number"] = str(i + 1)
                        row["Series Poster Image Name (including extension)"] = meta["series_poster"]
                        row["Series Landscape Image Name (including extension)"] = meta["series_landscape"]
                        row["Season Landscape Image Name (including extension)"] = meta["season_landscape"]

                    output_rows.append(row)
        
        # Save the final CSV for the provider
        if output_rows:
            save_csv(provider, output_rows, headers)
            print(f"✅ Generated {len(output_rows)} entries for {provider}")

    # 3. Create ZIP Archive
    
    # Filter for folders that were actually created/used in this run
    active_folders_to_zip = [f for f in all_generated_folders if os.path.exists(f) and os.listdir(f)]

    if not active_folders_to_zip:
        return None, "No files were generated based on the configuration. Check counts."

    # Create a unique ZIP file name in the main working directory
    zip_filename = f"mops-test-package-export-{uuid.uuid4().hex[:6]}.zip"
    zip_path = os.path.join(os.getcwd(), zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(OUTPUT_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                # Ensure the path in the ZIP is relative to the *root* of the generated packages
                zipf.write(full_path, os.path.relpath(full_path, OUTPUT_DIR))
                
    # Cleanup the individual generated folders after zipping (optional, but recommended)
    # shutil.rmtree(OUTPUT_DIR) 
    
    return zip_path, "Generation and Zipping complete."


def get_summary_data():
    """
    Collects summary data from the most recently generated packages.

    Returns:
        tuple: (content_summary_list, file_summary_list)
    """
    summary_table = []
    file_table = defaultdict(lambda: {"mp4": 0, "landscape": 0, "portrait": 0, "series": 0, "season": 0})
    
    # Check the common OUTPUT_DIR (GENERATED_PACKAGES)
    if not os.path.exists(OUTPUT_DIR):
        return [], []

    for provider in ["others", "warnerbros"]:
        folder = os.path.join(OUTPUT_DIR, provider)
        if not os.path.exists(folder):
            continue
            
        # Find the most recent CSV file in the folder
        csv_matches = glob.glob(os.path.join(folder, f"generated-{provider}-test-package-*.csv"))
        if not csv_matches:
            continue
            
        csv_file = max(csv_matches, key=os.path.getmtime)  # use most recent
        if not os.path.exists(csv_file):
            continue

        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            for row in rows:
                vtype = row.get("Video Type", "N/A").strip()
                product = row.get("products", "N/A")
                summary_table.append([provider, product, vtype])

                file_table_key = (provider, vtype)
                
                # File counts (assuming one of each per row, except for series/season)
                file_table[file_table_key]["mp4"] += 1
                file_table[file_table_key]["landscape"] += 1
                file_table[file_table_key]["portrait"] += 1

                if vtype.lower() == "full episode":
                    file_table[file_table_key]["series"] += 1
                    file_table[file_table_key]["season"] += 1

    content_counts = Counter(tuple(row) for row in summary_table)
    content_summary = [[*key, val] for key, val in content_counts.items()]
    
    file_summary_rows = []
    for (provider, vtype), counts in file_table.items():
        # Only count series/season images once per *series*, not per episode, 
        # but since we don't track unique series IDs here, the current *episode* count 
        # is the only thing we can report. For a simple summary, we show the number 
        # of rows that required those assets.
        
        # NOTE: Your original CLI script had a flaw in `summarize_results()` where it 
        # counted series/season images once per EPISODE. We maintain this behavior 
        # for consistency with your existing code's output.
        file_summary_rows.append([
            provider, vtype,
            counts["mp4"],
            counts["landscape"],
            counts["portrait"],
            counts["series"],
            counts["season"]
        ])
        
    return content_summary, file_summary_rows


# Remove the original `if __name__ == "__main__":` block entirely!