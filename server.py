import os
import sys
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

try:
    from backend.twitter_bot import TwitterBot
except ImportError:
    from twitter_bot import TwitterBot

app = Flask(__name__)
CORS(app)

bot = TwitterBot()
bot_thread = None

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(bot.get_status())

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"success": False, "message": "Kullanici adi ve sifre gerekli"}), 400
    
    result = bot.login(username, password)
    return jsonify(result)

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_thread
    
    if bot.is_running:
        return jsonify({"success": False, "message": "Bot zaten calisiyor"})
    
    data = request.get_json()
    hashtags = data.get('hashtags', [])
    settings = data.get('settings', {})
    credentials = data.get('credentials', {})
    
    if not hashtags:
        return jsonify({"success": False, "message": "En az bir hashtag gerekli"}), 400
    
    if not credentials.get('username') or not credentials.get('password'):
        return jsonify({"success": False, "message": "Twitter bilgileri gerekli"}), 400
    
    hashtag_tags = [h.get('tag', h) if isinstance(h, dict) else h for h in hashtags]
    
    bot_thread = threading.Thread(
        target=bot.run_bot,
        args=(hashtag_tags, settings, credentials),
        daemon=True
    )
    bot_thread.start()
    
    return jsonify({"success": True, "message": "Bot baslatildi"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    if not bot.is_running:
        return jsonify({"success": False, "message": "Bot zaten durmus"})
    
    bot.stop_bot()
    return jsonify({"success": True, "message": "Bot durduruldu"})

@app.route('/api/history', methods=['GET'])
def get_history():
    limit = request.args.get('limit', 100, type=int)
    history = bot.get_history(limit)
    return jsonify({"history": history})

@app.route('/api/test-login', methods=['POST'])
def test_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"success": False, "message": "Kullanici adi ve sifre gerekli"}), 400
    
    result = bot.login(username, password)
    return jsonify(result)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "TakipBot Backend calisiyor"})

@app.route('/api/reset', methods=['POST'])
def reset_bot():
    bot.cleanup()
    bot.follow_history = []
    bot.today_follows = 0
    bot.total_follows = 0
    bot.last_activity = None
    bot.save_data()
    return jsonify({"success": True, "message": "Bot sifirlandi"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', os.environ.get('BACKEND_PORT', 5001)))
    print(f"TakipBot Backend {port} portunda baslatiliyor...")
    app.run(host='0.0.0.0', port=port, debug=False)
