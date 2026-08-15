from waitress import serve

from app import app, initialize_audio


if __name__ == "__main__":
    initialize_audio()
    print("WiFi Soundboard is running at http://0.0.0.0:8080")
    serve(app, host="0.0.0.0", port=8080, threads=8)
