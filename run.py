import os
from dotenv import load_dotenv
from app import create_app

load_dotenv()

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"Relívia Modelar rodando em http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
