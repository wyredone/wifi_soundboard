from waitress import serve

from app import app, initialize_audio


if __name__ == "__main__":
    initialize_audio()
    print("WiFi Soundboard is running at http://0.0.0.0:48619")
    serve(app, host="0.0.0.0", port=48619, threads=8)
