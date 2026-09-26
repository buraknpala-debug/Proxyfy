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

def parse_decklist(decklist_text, cut_basic_lands=False):
    deck_dict = {}
    basic_lands = {"forest", "mountain", "plains", "island", "swamp", "snow-covered forest", "snow-covered mountain", "snow-covered plains", "snow-covered island", "snow-covered swamp"}
    
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
        
        if cut_basic_lands and name.lower() in basic_lands:
            continue
        
        deck_dict[name] = deck_dict.get(name, 0) + count
        
    return deck_dict

def get_card_data_smart_cascade(deck_dict, progress_bar, status_text, lang, art_style, set_code, fancy_mode):
    headers = {'User-Agent': 'Proxyfy/Smart-Cascade', 'Accept': 'application/json'}
    fetched_cards = {}
    error_log = {}
    
    remaining_names = list(deck_dict.keys())
    
    art_map = {
        "Borderless": "is:borderless",
        "Showcase": "is:showcase",
        "Retro": "is:retro",
        "Extended Art": "is:extendedart"
    }
    
    cascade_steps = []
    
    step_custom = {}
    if art_style != "Standard" and art_style in art_map: 
        step_custom['style'] = art_map[art_style]
    if set_code: 
        step_custom['set'] = set_code
    if lang != 'en': 
        step_custom['lang'] = lang
    if step_custom:
        cascade_steps.append(step_custom)
        
    if art_style != "Standard" and art_style in art_map and set_code:
        cascade_steps.append({'style': art_map[art_style], 'lang': lang if lang != 'en' else None})
        
    if set_code:
        cascade_steps.append({'set': set_code, 'lang': lang if lang != 'en' else None})
        
    if lang != 'en':
        cascade_steps.append({'lang': lang})
        
    cascade_steps.append({})
    
    current_step = 1
    total_steps = len(cascade_steps) + (1 if fancy_mode else 0)
    
    if fancy_mode:
        status_text.text("Analysiere Kartendaten für den Fancy-Modus (teuerste Artworks)...")
        still_missing = []
        chunks = [remaining_names[i:i + 20] for i in range(0, len(remaining_names), 20)]
        
        for chunk in chunks:
            or_query = " OR ".join([f'!"{name}"' for name in chunk])
            q = f"({or_query})"
            if set_code: q += f" e:{set_code}"
            
            time.sleep(0.15)
            try:
                response = requests.get("https://api.scryfall.com/cards/search", params={'q': q, 'unique': 'prints'}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    
                    for orig_name in chunk:
                        orig_lower = orig_name.lower()
                        matching_prints = []
                        
                        # Universeller Abgleich für MDFCs und Split-Karten
                        for card in data.get('data', []):
                            card_name = card['name'].lower()
                            faces = [f.strip() for f in card_name.split('//')]
                            if orig_lower == card_name or orig_lower in faces:
                                matching_prints.append(card)
                                
                        if matching_prints:
                            def get_price(c):
                                prices = c.get('prices', {})
                                p = prices.get('usd') or prices.get('usd_foil') or prices.get('eur') or "0"
                                try: return float(p)
                                except: return 0.0
                            matching_prints.sort(key=get_price, reverse=True)
                            fetched_cards[orig_name] = matching_prints[0]
                        else:
                            still_missing.append(orig_name)
                else:
                    still_missing.extend(chunk)
            except:
                still_missing.extend(chunk)
                
        remaining_names = list(dict.fromkeys(still_missing))
        current_step += 1

    for step_filters in cascade_steps:
        if not remaining_names:
            break
            
        status_text.text(f"Such-Kaskade Stufe {current_step}/{total_steps + len(cascade_steps)} ({len(remaining_names)} Karten übrig)...")
        chunks = [remaining_names[i:i + 20] for i in range(0, len(remaining_names), 20)]
        still_missing = []
        
        for chunk in chunks:
            or_query = " OR ".join([f'!"{name}"' for name in chunk])
            q = f"({or_query})"
            
            if 'style' in step_filters and step_filters['style']:
                q += f" {step_filters['style']}"
            if 'set' in step_filters and step_filters['set']:
                q += f" e:{step_filters['set']}"
            if 'lang' in step_filters and step_filters['lang']:
                q += f" lang:{step_filters['lang']}"
                
            time.sleep(0.15)
            try:
                response = requests.get("https://api.scryfall.com/cards/search", params={'q': q}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    found_in_batch = set()
                    
                    for orig_name in chunk:
                        orig_lower = orig_name.lower()
                        if orig_lower in found_in_batch:
                            continue
                            
                        # Universeller Abgleich für reguläre Kaskade
                        for card in data.get('data', []):
                            card_name = card['name'].lower()
                            faces = [f.strip() for f in card_name.split('//')]
                            
                            if orig_lower == card_name or orig_lower in faces:
                                if orig_name not in fetched_cards:
                                    fetched_cards[orig_name] = card
                                found_in_batch.add(orig_lower)
                                break
                                
                    for orig_name in chunk:
                        if orig_name.lower() not in found_in_batch:
                            still_missing.append(orig_name)
                else:
                    still_missing.extend(chunk)
            except Exception:
                still_missing.extend(chunk)
                
        remaining_names = list(dict.fromkeys(still_missing))
        current_step += 1
        
    error_log = {name: "Nicht gefunden" for name in remaining_names}
    
    card_metadata = []
    for name, count in deck_dict.items():
        if name in fetched_cards:
            card_data = fetched_cards[name]
            type_line = card_data.get('type_line', '')
            colors = card_data.get('colors')
            if colors is None and 'card_faces' in card_data:
                colors = card_data['card_faces'][0].get('colors', [])
            if colors is None:
                colors = []
                
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
                    'colors': colors,
                    'count': count
                })
                
    progress_bar.progress(1.0)
    return card_metadata, error_log

def download_image(url):
    headers = {'User-Agent': 'Proxyfy/Smart-Cascade'}
    img_response = requests.get(url, headers=headers)
    img = Image.open(BytesIO(img_response.content)).convert("RGBA")
    
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    corner_radius = int(img.size[0] * 0.045)
    draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=corner_radius, fill=255)
    
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=mask)
    return background

def generate_deck_pdf(deck_dict, output_filename, lang, art_style, set_code, fancy_mode):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    card_metadata, error_log = get_card_data_smart_cascade(deck_dict, progress_bar, status_text, lang, art_style, set_code, fancy_mode)
    
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

with st.sidebar:
    st.header("Spezifikationen")
    
    fancy_mode = st.checkbox("Fancy (Teuerstes/Seltenstes Artwork)", value=False)
    cut_basic_lands = st.checkbox("Standardländer ausschneiden", value=False)
    
    lang_input = st.selectbox("Sprache bevorzugt", ["English (en)", "Deutsch (de)", "Japanisch (ja)", "Französisch (fr)", "Spanisch (es)"])
    lang_code = lang_input.split("(")[1].replace(")", "")
    
    art_style = st.selectbox("Design überschreiben", ["Standard", "Extended Art", "Borderless", "Showcase", "Retro"])
    set_code = st.text_input("Spezifisches Set (Optional, z.B. 'mh2' oder '40k')", value="")

decklist_input = st.text_area("Füge deine Deckliste hier ein:", height=300)

if st.button("PDF Generieren", type="primary", use_container_width=True):
    if decklist_input.strip() == "":
        st.error("Bitte gib eine Deckliste ein.")
    else:
        deck_dict = parse_decklist(decklist_input, cut_basic_lands)
        pdf_filename = "Proxyfy_Deck.pdf"
        
        with st.spinner("Lade Kartendaten im Smart-Cascade-Modus..."):
            error_log, images_added = generate_deck_pdf(deck_dict, pdf_filename, lang_code, art_style, set_code.strip(), fancy_mode)
        
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
