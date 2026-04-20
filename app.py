#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM MATCH PREDICTOR BOT - Version avec indicateur clignotant "EN LIGNE"
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
last_greeting_day = None
last_status_message_id = None
status_animation_frame = 0

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
        return response.json().get('result', {}).get('message_id') if response.ok else None
    except Exception as e:
        print(f"❌ Erreur envoi: {e}")
        return None

def edit_message(message_id, text, keyboard=None):
    """Modifie un message existant"""
    if not message_id:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
    data = {
        'chat_id': CHAT_ID,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if keyboard:
        data['reply_markup'] = json.dumps(keyboard)
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

# ==================== INDICATEUR CLIGNOTANT ====================

def send_online_indicator():
    """Envoie l'indicateur de statut en ligne qui clignote"""
    global last_status_message_id
    
    message = """🟢 <b>╔══════════════════════════════════════════════════════════╗</b>
🟢 <b>║                                                          </b>
🟢 <b>║           🤖 BOT PRONOSTICS - EN LIGNE 🤖                </b>
🟢 <b>║                                                          </b>
🟢 <b>╚══════════════════════════════════════════════════════════╝</b>

<b>◐ RECHERCHE EN COURS... ◐</b>

⏳ Scan du site : <u>chaque seconde</u>
⚽ Matchs trouvés : <b>0</b>
📡 Statut : <b>ACTIF 24h/24</b>

┌──────────────────────────────────────────────────────────┐
│  💡 Le bot surveille automatiquement les matchs         │
│  🔔 Un message sera envoyé dès qu'un match apparaît     │
└──────────────────────────────────────────────────────────┘"""
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '📅 VOIR MATCHS', 'callback_data': 'refresh'}],
            [{'text': '🔄 STATUT', 'callback_data': 'status'}]
        ]
    }
    
    msg_id = send_message(message, keyboard)
    if msg_id:
        last_status_message_id = msg_id

def update_online_indicator():
    """Met à jour l'indicateur clignotant toutes les secondes"""
    global last_status_message_id, status_animation_frame, today_matches_cache, is_fetching
    
    if not last_status_message_id:
        return
    
    status_animation_frame += 1
    frames = ["◐", "◓", "◑", "◒"]
    dots = ["⚫", "🟢", "⚫", "🟢"]
    frame = frames[status_animation_frame % 4]
    dot = dots[status_animation_frame % 4]
    
    now = datetime.now()
    
    if is_fetching:
        status_icon = "🟡"
        status_text = "SCAN EN COURS"
    else:
        status_icon = "🟢"
        status_text = "ACTIF"
    
    message = f"""{status_icon} <b>╔══════════════════════════════════════════════════════════╗</b>
{status_icon} <b>║                                                          ║</b>
{status_icon} <b>║           🤖 BOT PRONOSTICS - {status_text} 🤖                ║</b>
{status_icon} <b>║                                                          ║</b>
{status_icon} <b>╚══════════════════════════════════════════════════════════╝</b>

<b>{frame} RECHERCHE EN COURS... {frame}</b>

⏳ Dernier scan : <b>{now.strftime('%H:%M:%S')}</b>
⚽ Matchs trouvés : <b>{len(today_matches_cache)}</b>
{dot} Statut : <b>{status_text}</b>
🔄 Vérification : <u>chaque seconde</u>

┌──────────────────────────────────────────────────────────┐
│  📡 Surveillance active 24h/24                          │
│  🔔 Nouveaux matchs = notification immédiate            │
└──────────────────────────────────────────────────────────┘"""
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '📅 VOIR MATCHS', 'callback_data': 'refresh'}],
            [{'text': '🔄 STATUT', 'callback_data': 'status'}]
        ]
    }
    
    edit_message(last_status_message_id, message, keyboard)

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
    """Récupère les matchs du jour - sans doublons"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        matches = []
        today = datetime.now().strftime('%d.%m.%Y')
        seen_teams = set()
        
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 3:
                date_text = cells[0].get_text(strip=True)
                if today in date_text:
                    teams = cells[1].get_text(strip=True)
                    
                    if teams in seen_teams:
                        continue
                    seen_teams.add(teams)
                    
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
        
        # Supprimer les doublons
        unique_matches = []
        seen = set()
        for match in matches:
            if match['teams'] not in seen:
                seen.add(match['teams'])
                unique_matches.append(match)
        
        return unique_matches
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
            [{'text': '📊 VOIR DÉTAILS', 'callback_data': 'details'}]
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
    
    if now.hour == 8 and now.minute == 0 and now.second < 30:
        if last_greeting_day != current_day:
            match_count = len(today_matches_cache)
            
            greeting_message = f"""
╔══════════════════════════════════════════════════════════╗
║                    🌞 BONJOUR ! 🌞                       ║
║              ⚽ Vos pronostics du jour !                 ║
║         📊 {match_count} match(s) disponible(s)                    ║
║   🎯 <b>Bonne journée et bons paris !</b>                  ║
╚══════════════════════════════════════════════════════════╝
"""
            if match_count > 0:
                greeting_message += "\n\n📋 <b>Matchs du jour :</b>\n"
                for idx, match in enumerate(today_matches_cache[:5], 1):
                    greeting_message += f"\n{idx}. {match['teams']} - 🎯 {match['prediction']}"
                if match_count > 5:
                    greeting_message += f"\n\n... et {match_count - 5} autre(s) match(s)"
            
            send_message(greeting_message, get_keyboard())
            last_greeting_day = current_day
            print(f"🌞 Message de bienvenue envoyé - {match_count} match(s)")
            return True
    return False

# ==================== SURVEILLANCE ====================

def check_and_update():
    """Vérifie les nouveaux matchs - chaque seconde"""
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
          🔔 Match ajouté automatiquement                                                                         
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

def online_indicator_loop():
    """Boucle pour l'indicateur clignotant - toutes les 1 seconde"""
    print("🟢 Indicateur de statut en ligne - mise à jour chaque seconde")
    while True:
        try:
            update_online_indicator()
            time.sleep(1)
        except Exception as e:
            print(f"❌ Erreur indicateur: {e}")
            time.sleep(5)

def bot_loop():
    """Boucle principale - vérifie chaque seconde"""
    print("🔄 Bot démarré - Surveillance active toutes les secondes")
    
    while True:
        try:
            check_and_update()
            send_daily_greeting()
            time.sleep(1)
        except Exception as e:
            print(f"❌ Erreur boucle: {e}")
            time.sleep(5)

# ==================== ROUTES FLASK ====================

@app.route('/')
def home():
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
    return jsonify({
        'status': 'healthy', 
        'time': datetime.now().isoformat(),
        'matches': len(today_matches_cache)
    })

@app.route('/test-greeting')
def test_greeting():
    send_daily_greeting()
    return jsonify({'status': 'greeting sent'})

@app.route('/status')
def status():
    return jsonify({
        'online': True,
        'matches': len(today_matches_cache),
        'last_scan': datetime.now().strftime('%H:%M:%S'),
        'fetching': is_fetching
    })

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
    
    # Envoyer l'indicateur de statut en ligne
    send_online_indicator()
    time.sleep(2)
    
    # Démarrer l'indicateur clignotant (toutes les 1 seconde)
    indicator_thread = threading.Thread(target=online_indicator_loop, daemon=True)
    indicator_thread.start()
    
    # Démarrer le bot
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    
    print("=" * 50)
    print("🤖 BOT PRONOSTICS - VERSION CORRIGÉE")
    print("=" * 50)
    print(f"✅ Bot démarré avec succès!")
    print(f"🔄 Vérification: chaque seconde")
    print(f"🟢 Indicateur clignotant: toutes les 1 seconde")
    print(f"📊 Éviter les doublons: activé")
    print("=" * 50)
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
