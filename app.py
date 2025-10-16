import os
from flask import Flask, render_template, request, redirect, url_for, send_file, flash

# Import the modified generation functions
from generator import run_generation, get_summary_data

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = 'supersecretkey' # Required for flash messages and session management
app.config['OUTPUT_DIR'] = os.path.join(os.getcwd(), "GENERATED_PACKAGES")

# Defined providers for the manual configuration form
AVAILABLE_PROVIDERS = {
    "others": ["localnow", "twc", "hbcugo"],
    "warnerbros": ["localnow"]
}

# --- ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        mode = request.form.get('mode')
        if mode == 'default':
            return redirect(url_for('generate', mode='default'))
        elif mode == 'manual':
            return redirect(url_for('manual_config'))
        else:
            flash("Invalid mode selected.", 'danger')
            return redirect(url_for('home'))
    
    return render_template('home.html')

@app.route('/manual_config', methods=['GET', 'POST'])
def manual_config():
    # If the user is submitting the form, it will POST to /generate
    # This route is only for displaying the form.
    
    return render_template('manual_config.html', providers=AVAILABLE_PROVIDERS)

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    zip_path = None
    
    if request.method == 'GET':
        # Default Mode Logic (called via GET redirect from home)
        mode = request.args.get('mode')
        if mode == 'default':
            zip_path, message = run_generation('default')
        else:
            flash("Generation mode not specified.", 'danger')
            return redirect(url_for('home'))
    
    elif request.method == 'POST':
        # Manual Mode Logic (called via POST from manual_config.html)
        mode = request.form.get('mode')
        if mode == 'manual':
            manual_configs = {}
            
            # Reconstruct the manual config dictionary from form data
            for provider, products in AVAILABLE_PROVIDERS.items():
                provider_has_config = False
                manual_configs[provider] = {}
                for product in products:
                    product_config = {}
                    movie_count = request.form.get(f'{provider}_{product}_full_movie', '0')
                    episode_count = request.form.get(f'{provider}_{product}_full_episode', '0')
                    short_count = request.form.get(f'{provider}_{product}_short_video', '0')
                    
                    if int(movie_count) > 0 or int(episode_count) > 0 or int(short_count) > 0:
                        provider_has_config = True
                    
                    # Ensure counts are passed as integers or castable strings
                    product_config['full_movie'] = movie_count
                    product_config['full_episode'] = episode_count
                    
                    if provider == "others" and product == "twc":
                        product_config['short_video'] = short_count
                    
                    manual_configs[provider][product] = product_config
                
                # Remove providers that were selected but had all zero counts
                if not provider_has_config:
                    del manual_configs[provider]
            
            if not manual_configs:
                flash("Please enter at least one content count in Manual Mode.", 'warning')
                return redirect(url_for('manual_config'))
            
            # Run the generation with the extracted manual configuration
            zip_path, message = run_generation('manual', manual_configs)

    if not zip_path:
        flash(f"Error during generation: {message}", 'danger')
        return redirect(url_for('home'))

    # If generation was successful, get summary data and show results
    content_summary, file_summary = get_summary_data()
    
    return render_template(
        'results.html', 
        zip_filename=os.path.basename(zip_path),
        content_summary=content_summary,
        file_summary=file_summary
    )

@app.route('/download/<path:filename>', methods=['GET'])
def download(filename):
    # The ZIP file is created in the main working directory (where app.py runs)
    full_path = os.path.join(os.getcwd(), filename) 
    
    if os.path.exists(full_path):
        return send_file(full_path, as_attachment=True)
    else:
        flash("The generated package file was not found.", 'danger')
        return redirect(url_for('home'))

if __name__ == '__main__':
    # You might need to install flask: pip install Flask
    app.run(debug=True)