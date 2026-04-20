#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM MATCH PREDICTOR BOT - Version pour Render.com avec message à 8h
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import json
import os
import re
import threading
from flask import Flask, jsonify

app = Flask(__name__)

# ==================== CONFIGURATION ====================
TOKEN = "8540465521:AAFn4Y0tpl-emOkacL8hTEzxPFiigTYRXYA"
CHAT_ID = "7136644322"
URL = 'https://cryptofixedmatch.com/'

# Variables
last_match_ids = set()
today_matches_cache = []
is_fetching = False
MATCH_STATE_FILE = 'match_state.json'
last_greeting_day = None  # Pour suivre le dernier jour où le message a été envoyé

# ==================== FONCTIONS TELEGRAM ====================

def send_message(text, keyboard=None):
    """Envoie un message Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    if keyboard:
        data['reply_markup'] = json.dumps(keyboard)
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"✅ Message envoyé")
        return response
    except Exception as e:
        print(f"❌ Erreur envoi: {e}")
        return None

# ==================== FONCTIONS DE SCRAPING ====================

def get_match_icon(match_time):
    """Retourne l'icône selon l'heure"""
    try:
        current_hour = datetime.now().hour
        if ':' in match_time:
            match_hour = int(match_time.split(':')[0])
            if match_hour < current_hour:
                return "✅"
            elif match_hour == current_hour:
                return "🔴"
            return "⏳"
    except:
        pass
    return "⚽"

def get_today_matches():
    """Récupère les matchs du jour"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        matches = []
        today = datetime.now().strftime('%d.%m.%Y')
        
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 3:
                date_text = cells[0].get_text(strip=True)
                if today in date_text:
                    teams = cells[1].get_text(strip=True)
                    prediction = cells[2].get_text(strip=True)
                    odds = cells[3].get_text(strip=True) if len(cells) > 3 else 'N/A'
                    
                    time_match = re.search(r'(\d{1,2}:\d{2})', date_text)
                    match_time = time_match.group(1) if time_match else '--:--'
                    
                    matches.append({
                        'id': f"{teams}_{today}",
                        'teams': teams,
                        'prediction': prediction,
                        'odds': odds,
                        'date': today,
                        'time': match_time
                    })
        return matches
    except Exception as e:
        print(f"❌ Erreur scraping: {e}")
        return []

def create_match_display():
    """Crée l'affichage des matchs"""
    global today_matches_cache
    now = datetime.now()
    
    display = f"""
╔══════════════════════════════════════════════════════════╗
║        📅 MATCHS DU {now.strftime('%d/%m/%Y')}        🕐 {now.strftime('%H:%M:%S')}     ║
╚══════════════════════════════════════════════════════════╝

"""
    
    if not today_matches_cache:
        display += "┌──────────────────────────────────────────────────────────┐\n"
        display += "│                     🔄 Aucun match                        │\n"
        display += "│                 Recherche en cours...                     │\n"
        display += "└──────────────────────────────────────────────────────────┘\n"
        return display
    
    for idx, match in enumerate(today_matches_cache, 1):
        icon = get_match_icon(match['time'])
        display += f"""
┌────────────────────────── MATCH N°{idx} ──────────────────────────┐
│   {icon}  <b>{match['teams']}</b>
│   🎯  Pronostic : {match['prediction']}
│   💰  Cote     : {match['odds']}
│   🕐  Horaire  : {match['time']}
│   📅  Date     : {match['date']}
└────────────────────────────────────────────────────────────────────┘
"""
    
    display += f"""
┌──────────────────────────────────────────────────────────┐
│   📊 Total : {len(today_matches_cache)} match(s) trouvé(s)                     │
│   🔄 Mise à jour : chaque seconde                        │
│   ⏳ Prochainement : d'autres matchs peuvent apparaître   │
└──────────────────────────────────────────────────────────┘
"""
    return display

def get_keyboard():
    """Clavier d'actions"""
    return {
        'inline_keyboard': [
            [{'text': '🔄 ACTUALISER', 'callback_data': 'refresh'}],
            [{'text': '📊 DÉTAILS', 'callback_data': 'details'}]
        ]
    }

def update_main_display():
    """Met à jour l'affichage principal"""
    display = create_match_display()
    keyboard = get_keyboard()
    send_message(display, keyboard)

# ==================== MESSAGE QUOTIDIEN À 8H ====================

def send_daily_greeting():
    """Envoie le message de bienvenue à 8h00 chaque jour"""
    global last_greeting_day, today_matches_cache
    
    now = datetime.now()
    current_day = now.day
    
    # Vérifier si c'est 8h00 et si on n'a pas déjà envoyé aujourd'hui
    if now.hour == 8 and now.minute == 0 and now.second < 30:
        if last_greeting_day != current_day:
            # Compter les matchs du jour
            match_count = len(today_matches_cache)
            
            # Créer le message de bienvenue
            greeting_message = f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║                    🌞 BONJOUR ! 🌞                       ║
║                                                          ║
║              ⚽ Vos pronostics du jour !                 ║
║                                                          ║
║         📊 {match_count} match(s) disponible(s)                    ║
║                                                          ║
║   📅 Aujourd'hui : {now.strftime('%d/%m/%Y')}                     ║
║   🕐 Heure : {now.strftime('%H:%M:%S')}                             ║
║                                                          ║
║   👆 Consultez les matchs ci-dessus                       ║
║   🔄 Mise à jour automatique chaque seconde               ║
║                                                          ║
║   🎯 <b>Bonne journée et bons paris !</b>                  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
            # Ajouter la liste des matchs s'il y en a
            if match_count > 0:
                greeting_message += "\n\n📋 <b>Matchs du jour :</b>\n"
                for idx, match in enumerate(today_matches_cache[:5], 1):
                    greeting_message += f"\n{idx}. {match['teams']} - 🎯 {match['prediction']}"
                if match_count > 5:
                    greeting_message += f"\n\n... et {match_count - 5} autre(s) match(s)"
            
            # Envoyer le message
            send_message(greeting_message, get_keyboard())
            last_greeting_day = current_day
            print(f"🌞 Message de bienvenue envoyé à {now.strftime('%H:%M:%S')} - {match_count} match(s)")
            return True
    
    return False

# ==================== SURVEILLANCE ====================

def check_and_update():
    """Vérifie les nouveaux matchs"""
    global last_match_ids, today_matches_cache, is_fetching
    
    if is_fetching:
        return
    
    is_fetching = True
    
    try:
        current_matches = get_today_matches()
        current_ids = {m['id'] for m in current_matches}
        new_matches = [m for m in current_matches if m['id'] not in last_match_ids]
        
        if new_matches:
            print(f"🎉 +{len(new_matches)} nouveau(x) match(s) à {datetime.now().strftime('%H:%M:%S')}")
            
            for match in new_matches:
                icon = get_match_icon(match['time'])
                notification = f"""
╔════════════════════ NOUVEAU MATCH ════════════════════╗
║   {icon} <b>{match['teams']}</b>
║   🎯 {match['prediction']}
║   💰 {match['odds']}  🕐 {match['time']}
╚═══════════════════════════════════════════════════════╝
"""
                send_message(notification)
                time.sleep(0.5)
            
            today_matches_cache = current_matches
            update_main_display()
        
        last_match_ids = current_ids
        
        with open(MATCH_STATE_FILE, 'w') as f:
            json.dump({'last_match_ids': list(last_match_ids)}, f)
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    is_fetching = False

def bot_loop():
    """Boucle principale - vérifie chaque seconde"""
    print("🔄 Bot démarré - Surveillance active toutes les secondes")
    print("🌞 Message de bienvenue programmé à 08h00 chaque jour")
    
    while True:
        try:
            # Vérifier les nouveaux matchs
            check_and_update()
            
            # Vérifier et envoyer le message quotidien à 8h
            send_daily_greeting()
            
            # Attendre 1 seconde
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Erreur boucle: {e}")
            time.sleep(5)

# ==================== ROUTES FLASK ====================

@app.route('/')
def home():
    """Page d'accueil pour vérifier que le bot tourne"""
    return jsonify({
        'status': 'online',
        'bot_name': 'Telegram Match Predictor',
        'matches_today': len(today_matches_cache),
        'last_update': datetime.now().strftime('%H:%M:%S'),
        'daily_greeting': '08h00 chaque jour',
        'message': 'Bot actif! Les matchs sont surveillés chaque seconde'
    })

@app.route('/health')
def health():
    """Vérification de santé pour Render"""
    return jsonify({
        'status': 'healthy', 
        'time': datetime.now().isoformat(),
        'greeting_sent': last_greeting_day is not None
    })

@app.route('/test-greeting')
def test_greeting():
    """Route de test pour envoyer le message manuellement"""
    send_daily_greeting()
    return jsonify({'status': 'greeting sent'})

# ==================== MAIN ====================

if __name__ == '__main__':
    # Charger l'état précédent
    if os.path.exists(MATCH_STATE_FILE):
        try:
            with open(MATCH_STATE_FILE, 'r') as f:
                data = json.load(f)
                last_match_ids = set(data.get('last_match_ids', []))
                print(f"📂 État chargé: {len(last_match_ids)} match(s) en mémoire")
        except:
            pass
    
    # Envoyer message de démarrage
    send_message("✅ Bot démarré sur Render.com !\n\n🔄 Surveillance active des matchs toutes les secondes.\n🌞 Message de bienvenue chaque jour à 08h00.")
    
    # Démarrer le bot dans un thread séparé
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    
    print("=" * 50)
    print("🤖 BOT PRONOSTICS - SUR RENDER.COM")
    print("=" * 50)
    print(f"✅ Bot démarré avec succès!")
    print(f"🔄 Vérification: chaque seconde")
    print(f"🌞 Message quotidien: 08h00")
    print(f"📱 Telegram: actif")
    print("=" * 50)
    
    # Démarrer le serveur Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)