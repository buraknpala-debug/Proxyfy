import streamlit as st
import os
import re
import time
import requests
import concurrent.futures
from io import BytesIO
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

# --- Konfiguration ---
CARD_WIDTH = 63 * mm
CARD_HEIGHT = 88 * mm
MARGIN_X = 10 * mm
MARGIN_Y = 15 * mm
SPACING = 2 * mm 

def parse_decklist(decklist_text):
    deck_dict = {}
    lines = decklist_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if re.match(r'^(sideboard|commander|maybeboard|mainboard|companion)', line, re.IGNORECASE):
            continue
            
        count_match = re.match(r'^(\d+)[xX]?\s+(.+)$', line)
        if count_match:
            count = int(count_match.group(1))
            rest = count_match.group(2).strip()
        else:
            count = 1
            rest = line.strip()
            
        if '(' in rest:
            name = rest.split('(')[0].strip()
        else:
            name = rest.split('*')[0].strip()
            
        name = name.replace('*', '').strip()
        name = name.split(' / ')[0].split(' // ')[0].strip()
        
        deck_dict[name] = deck_dict.get(name, 0) + count
        
    return deck_dict

def get_scryfall_bulk_data(deck_dict, progress_bar, status_text, lang, art_style, set_code):
    """Nutzt die Scryfall Collection API in sicheren 50er-Blöcken inklusive Sprach- und Design-Steuerung."""
    headers = {'User-Agent': 'Proxyfy/Beta-Bulk', 'Accept': 'application/json'}
    
    card_metadata = []
    error_log = {}
    
    identifiers = [{"name": name} for name in deck_dict.keys()]
    chunks = [identifiers[i:i + 50] for i in range(0, len(identifiers), 50)]
    
    total_chunks = len(chunks)
    fetched_cards = {}
    
    for idx, chunk in enumerate(chunks):
        status_text.text(f"Lade Kartengruppe {idx + 1} von {total_chunks}...")
        try:
            response = requests.post(
                "https://api.scryfall.com/cards/collection",
                json={"identifiers": chunk},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                for card in data.get('data', []):
                    fetched_cards[card['name'].lower()] = card
                for not_found in data.get('not_found', []):
                    error_log[not_found.get('name', 'Unbekannt')] = "In der Collection nicht gefunden"
            else:
                for item in chunk:
                    error_log[item['name']] = f"HTTP Fehler {response.status_code}"
        except Exception as e:
            for item in chunk:
                error_log[item['name']] = str(e)
                
        progress_bar.progress((idx + 1) / total_chunks)
        time.sleep(0.15)
        
    for name, count in deck_dict.items():
        card_data = fetched_cards.get(name.lower())
        
        # Falls Sprache oder Set/Design erzwungen wird, über die Such-API nachsteuern falls nötig
        if card_data and (lang != 'en' or art_style != "Standard" or set_code):
            q = f'!"{name}"'
            if lang != 'en': q += f' lang:{lang}'
            if set_code: q += f' e:{set_code}'
            art_map = {"Borderless": "is:borderless", "Showcase": "is:showcase", "Retro": "is:retro", "Extended Art": "is:extendedart"}
            if art_style != "Standard": q += f' {art_map[art_style]}'
            
            try:
                res = requests.get("https://api.scryfall.com/cards/search", params={'q': q}, headers=headers)
                if res.status_code == 200:
                    search_data = res.json()
                    if 'data' in search_data and len(search_data['data']) > 0:
                        card_data = search_data['data'][0]
            except Exception:
                pass

        if not card_data:
            if name not in error_log:
                error_log[name] = "Nicht gefunden"
            continue
            
        type_line = card_data.get('type_line', '')
        colors = card_data.get('colors')
        if colors is None and 'card_faces' in card_data:
            colors = card_data['card_faces'][0].get('colors', [])
        
        img_urls = []
        if 'image_uris' in card_data:
            img_urls.append(card_data['image_uris'].get('png', card_data['image_uris'].get('large')))
        elif 'card_faces' in card_data:
            for face in card_data['card_faces']:
                face_url = face.get('image_uris', {}).get('png', face.get('image_uris', {}).get('large'))
                if face_url:
                    img_urls.append(face_url)
                    
        if img_urls:
            card_metadata.append({
                'name': name,
                'urls': img_urls,
                'type': type_line,
                'colors': colors if colors else [],
                'count': count
            })
            
    return card_metadata, error_log

def download_image(url):
    headers = {'User-Agent': 'Proxyfy/Beta-Bulk'}
    img_response = requests.get(url, headers=headers)
    img = Image.open(BytesIO(img_response.content)).convert("RGBA")
    
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    corner_radius = int(img.size[0] * 0.045)
    draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=corner_radius, fill=255)
    
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=mask)
    return background

def generate_deck_pdf(deck_dict, output_filename, lang, art_style, set_code):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    card_metadata, error_log = get_scryfall_bulk_data(deck_dict, progress_bar, status_text, lang, art_style, set_code)
    
    if not card_metadata:
        status_text.text("Keine Karten gefunden.")
        return error_log, 0
        
    def sort_key(c):
        main_type = c['type'].split('—')[0].lower()
        num_colors = len(c['colors'])
        if 'basic land' in main_type: return 90
        elif 'land' in main_type: return 80
        elif 'creature' in main_type:
            if num_colors > 1: return 10 - num_colors 
            elif num_colors == 1: return 15
            else: return 20
        elif 'planeswalker' in main_type: return 30
        elif 'instant' in main_type or 'sorcery' in main_type: return 40
        elif 'enchantment' in main_type: return 50
        elif 'artifact' in main_type: return 60
        else: return 70
        
    card_metadata.sort(key=sort_key)
    
    status_text.text("Verarbeite Bilddateien und generiere PDF...")
    progress_bar.progress(0.0)
    
    c = canvas.Canvas(output_filename, pagesize=A4)
    x_start = MARGIN_X
    y_start = A4[1] - MARGIN_Y - CARD_HEIGHT
    col = 0
    row = 0
    images_added = 0
    
    total_downloads = sum(len(item['urls']) for item in card_metadata)
    downloaded = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in card_metadata:
            future_to_url = {executor.submit(download_image, url): url for url in item['urls']}
            downloaded_images = []
            
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    downloaded_images.append(future.result())
                except Exception:
                    pass
                downloaded += 1
                if total_downloads > 0:
                    progress_bar.progress(downloaded / total_downloads)
                
            for _ in range(item['count']):
                for img in downloaded_images:
                    x = x_start + col * (CARD_WIDTH + SPACING)
                    y = y_start - row * (CARD_HEIGHT + SPACING)
                    
                    img_reader = ImageReader(img)
                    c.drawImage(img_reader, x, y, width=CARD_WIDTH, height=CARD_HEIGHT)
                    images_added += 1
                    
                    col += 1
                    if col > 2:
                        col = 0
                        row += 1
                        
                    if row > 2:
                        c.showPage()
                        col = 0
                        row = 0

    if images_added > 0:
        c.save()
        status_text.text("PDF-Generierung erfolgreich abgeschlossen.")
        
    return error_log, images_added

# ==========================================
# STREAMLIT BENUTZEROBERFLÄCHE
# ==========================================

st.set_page_config(page_title="Proxyfy Beta by Nefpo", layout="wide")

st.title("Proxyfy Beta by Nefpo")
st.write("Generiere druckfertige PDFs in verlustfreier PNG-Qualität.")

# Seitenleiste für Einstellungen (Sprache, Design, Edition)
with st.sidebar:
    st.header("Spezifikationen")
    lang_input = st.selectbox("Sprache bevorzugt", ["English (en)", "Deutsch (de)", "Japanisch (ja)", "Französisch (fr)", "Spanisch (es)"])
    lang_code = lang_input.split("(")[1].replace(")", "")
    
    art_style = st.selectbox("Design überschreiben", ["Standard", "Extended Art", "Borderless", "Showcase", "Retro"])
    set_code = st.text_input("Spezifisches Set (Optional, z.B. 'mh2' oder '40k')", value="")

# Hauptbereich für Deckliste und Generierung
decklist_input = st.text_area("Füge deine Deckliste hier ein:", height=300)

if st.button("PDF Generieren", type="primary", use_container_width=True):
    if decklist_input.strip() == "":
        st.error("Bitte gib eine Deckliste ein.")
    else:
    # Restlicher Ablauf
        deck_dict = parse_decklist(decklist_input)
        pdf_filename = "Proxyfy_Deck.pdf"
        
        with st.spinner("Lade Kartendaten..."):
            error_log, images_added = generate_deck_pdf(deck_dict, pdf_filename, lang_code, art_style, set_code.strip())
        
        if error_log:
            st.warning("Folgende Karten verursachten Fehler:")
            for card, err in error_log.items():
                st.write(f"- {card}: {err}")
        
        if images_added > 0 and os.path.exists(pdf_filename):
            with open(pdf_filename, "rb") as pdf_file:
                st.download_button(
                    label="PDF herunterladen",
                    data=pdf_file,
                    file_name="Proxyfy_Deck.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            st.success(f"Erfolg: {images_added} Karten generiert.")

# Dezent platzierter Werbe- und Sponsorenbereich am unteren Rand
#st.markdown("---")
#st.markdown("### Sponsor / Werbung")
#col_ad1, col_ad2 = st.columns([3, 1])
#with col_ad1:
#    st.info("Platzhalter für zukünftige Banner oder Werbepartner. Perfekt geeignet, um die Anwendung bei einem Online-Release zu unterstützen.")
#with col_ad2:
#    st.write("Anzeige (Platzhalter)")