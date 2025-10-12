# C:\Projects\payslip\app.py
from flask import Flask, send_from_directory, request, send_file, jsonify
import os, tempfile, traceback, glob, shutil, threading, webbrowser, time
from werkzeug.utils import secure_filename

# Import the generator module directly (must be in same folder)
import payslipGenerator

app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# Serve React index
@app.route('/')
def serve_react():
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(_):
    return send_from_directory(app.static_folder, 'index.html')

# API
@app.route('/api/generate_payslip', methods=['POST'])
def generate_payslip():
    try:
        company = request.form.get('company_name')
        address = request.form.get('company_address')
        month = request.form.get('payslip_month')
        location = request.form.get('location')
        file = request.files.get('salary_file')

        if not all([company, address, month, location, file]):
            return jsonify({'message': 'All fields are required.'}), 400

        # Save uploaded Excel to temporary folder
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(file_path)
        print(f"[Flask] Uploaded file saved to: {file_path}")

        # Call the generator function directly (non-interactive)
        # It will create a ZIP in the same folder as file_path (base_dir)
        try:
            payslipGenerator.process_file(file_path, company, address, month, location)
        except Exception as gen_err:
            traceback.print_exc()
            return jsonify({'message': 'Generator error', 'error': str(gen_err)}), 500

        # Locate the generated ZIP (temp_dir first, then project folder)
        possible_zips = glob.glob(os.path.join(temp_dir, "Payslips_*.zip"))
        if not possible_zips:
            project_zips = glob.glob(os.path.join('C:/Projects/payslip', "Payslips_*.zip"))
            possible_zips.extend(project_zips)

        if not possible_zips:
            return jsonify({'message': 'ZIP not found after generation.'}), 500

        latest_zip = max(possible_zips, key=os.path.getctime)
        print(f"[Flask] Found ZIP: {latest_zip}")

        # Archive to permanent folder
        archive_folder = os.path.join('C:/Projects/payslip', 'generated_zips')
        os.makedirs(archive_folder, exist_ok=True)
        archived_zip = os.path.join(archive_folder, os.path.basename(latest_zip))
        shutil.copy(latest_zip, archived_zip)
        print(f"[Flask] Archived ZIP copied to: {archived_zip}")

        # Prepare response
        response = send_file(latest_zip, as_attachment=True)

        # Cleanup temp (uploaded excel + temp zip + folder)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if temp_dir in latest_zip and os.path.exists(latest_zip):
                os.remove(latest_zip)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            print(f"[Cleanup] Removed temp files in {temp_dir}")
        except Exception as cleanup_err:
            print(f"[Cleanup Warning] {cleanup_err}")

        return response

    except Exception as e:
        traceback.print_exc()
        return jsonify({'message': 'Server error', 'error': str(e)}), 500


def _open_browser_later(url, delay=1.0):
    """Open default browser after a small delay in a separate thread."""
    def _target():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[Browser Open] could not open browser: {e}")
    t = threading.Thread(target=_target)
    t.daemon = True
    t.start()


if __name__ == '__main__':
    host = '127.0.0.1'
    port = 5000
    url = f"http://{host}:{port}"
    print(f"🚀 Starting Payslip app at {url}")
    # Open browser once (do not use reloader or debug mode that spawns two processes)
    _open_browser_later(url, delay=1.2)
    # IMPORTANT: use_reloader=False to avoid double-opening and duplicate process
    app.run(debug=False, use_reloader=False, host=host, port=port)
