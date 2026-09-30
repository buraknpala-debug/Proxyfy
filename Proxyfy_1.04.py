import streamlit as st
import streamlit.components.v1 as components
import os
import re
import time
import requests
import concurrent.futures
import copy
from io import BytesIO
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, legal
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from typing import List, Dict, Tuple, Any

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
CARD_WIDTH = 63 * mm
CARD_HEIGHT = 88 * mm
MARGIN_X = 5 * mm
MARGIN_Y = 5 * mm

# Ausgelagertes, sauberes CSS (Macht den Code unten viel lesbarer)
CSS_STYLES = """
<style>
    div, button, input, textarea, select, img, span, ul, li { border-radius: 0px !important; }
    div[data-baseweb="radio"] div[aria-checked="true"] > div,
    div[data-baseweb="checkbox"] div[aria-checked="true"] > div { background-color: #FCEE0A !important; border-color: #FCEE0A !important; }
    div[data-baseweb="radio"] div[aria-checked="true"] > div > div { background-color: #050505 !important; }
    div[data-baseweb="checkbox"] div[aria-checked="true"] > div svg { fill: #050505 !important; color: #050505 !important; }
    div[data-baseweb="select"] > div { border: 1px solid #333333 !important; background-color: transparent !important; }
    div[data-baseweb="select"] > div:focus-within { border-color: #FCEE0A !important; box-shadow: 0 0 4px #FCEE0A40 !important; }
    div[data-baseweb="popover"] > div, ul[role="listbox"] { background-color: #111111 !important; border-radius: 0px !important; border: 1px solid #FCEE0A !important; }
    ul[role="listbox"] li[aria-selected="true"] { background-color: #FCEE0A30 !important; color: #FCEE0A !important; }
    ul[role="listbox"] li:hover { background-color: #FCEE0A20 !important; }
    div[data-baseweb="input"] > div, textarea { border: 1px solid #333333 !important; }
    div[data-baseweb="input"] > div:focus-within, textarea:focus { border: 1px solid #FCEE0A !important; box-shadow: 0 0 4px #FCEE0A40 !important; }
    input[type="number"] { text-align: center !important; }
    div[data-testid="stHorizontalBlock"] { align-items: stretch !important; }
    [data-testid="column"] { display: flex !important; flex-direction: column !important; height: 100% !important; }
    [data-testid="column"] > div.element-container:last-of-type, [data-testid="column"] > div:last-child { margin-top: auto !important; }
    div[data-testid="stImage"] img { width: 100% !important; height: auto !important; aspect-ratio: 63 / 88 !important; object-fit: contain !important; display: block; border: 1px solid #222222; transition: all 0.2s; margin-bottom: 5px; }
    div[data-testid="stImage"] img:hover { border: 1px solid #FCEE0A; box-shadow: 0 0 6px #FCEE0A40; transform: scale(1.01); }
    div[data-testid="stButton"] > button[kind="primary"] { background-color: transparent !important; color: #FCEE0A !important; border: 2px solid #FCEE0A !important; text-transform: uppercase; font-weight: bold; letter-spacing: 2px; box-shadow: 0 0 3px #FCEE0A30; transition: all 0.2s ease-in-out; }
    div[data-testid="stButton"] > button[kind="primary"]:hover { background-color: #FCEE0A !important; color: #000000 !important; box-shadow: 0 0 8px #FCEE0A, 0 0 15px #FCEE0A60 !important; }
    div[data-testid="stButton"] > button[kind="secondary"] { background-color: transparent !important; color: #E0E0E0 !important; border: 1px solid #444444 !important; transition: all 0.2s ease-in-out; padding: 2px 10px; width: 100%; }
    div[data-testid="stButton"] > button[kind="secondary"]:hover { border: 1px solid #FCEE0A !important; color: #FCEE0A !important; box-shadow: 0 0 5px #FCEE0A40 !important; }
    .stProgress > div > div > div > div, [data-testid="stProgress"] div[role="progressbar"] > div > div { background-color: #FCEE0A !important; box-shadow: 0 0 8px #FCEE0A !important; }
    a.tp-to-top-btn { display: flex !important; align-items: center !important; justify-content: center !important; position: fixed !important; bottom: 80px !important; right: 30px !important; width: auto !important; background-color: #050505 !important; color: #FCEE0A !important; border: 2px solid #FCEE0A !important; padding: 10px 20px !important; font-size: 14px !important; font-weight: bold !important; text-align: center !important; text-decoration: none !important; text-transform: uppercase !important; letter-spacing: 2px !important; z-index: 999999 !important; transition: all 0.2s ease-in-out !important; box-shadow: 0 0 15px rgba(0,0,0,0.8) !important; }
    a.tp-to-top-btn:hover { background-color: #FCEE0A !important; color: #000000 !important; box-shadow: 0 0 15px #FCEE0A80, 0 0 8px #FCEE0A !important; }
    .group-title { color: #FCEE0A; font-size: 20px; font-weight: bold; margin-top: 40px; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 2px; text-shadow: 0 0 8px rgba(252, 238, 10, 0.4); }
    div[data-testid="stVerticalBlock"]:has(.card-group-marker):not(:has(div[data-testid="stVerticalBlock"]:has(.card-group-marker))) { border: 1px solid rgba(252, 238, 10, 0.15) !important; box-shadow: 0 0 10px rgba(252, 238, 10, 0.05) !important; padding: 15px !important; margin-bottom: 20px !important; background-color: rgba(5, 5, 5, 0.3) !important; border-radius: 5px !important; }
    .card-group-marker, .card-grid-marker { display: none; }
    div[data-testid="column"]:has(.card-grid-marker):not(:has(div[data-testid="column"]:has(.card-grid-marker))) { container-type: inline-size; container-name: cardcol; }
    div[data-testid="column"]:has(.card-grid-marker) div[data-testid="stButton"] button p { font-size: 0px !important; color: transparent !important; margin: 0; padding: 0; }
    div[data-testid="column"]:has(.card-grid-marker) div[data-testid="stButton"] button p::after { content: "CHANGE ART ⇄"; font-size: 13px !important; color: #FCEE0A !important; text-transform: uppercase; letter-spacing: 1px; visibility: visible; }
    @container cardcol (max-width: 140px) { div[data-testid="column"]:has(.card-grid-marker) div[data-testid="stButton"] button p::after { content: "⇄"; font-size: 18px !important; } }
    @keyframes shapeJump { 0%, 10.55% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,10 85,70 15,70" fill="none" stroke="%23FCEE0A" stroke-width="8" stroke-linejoin="round"/></svg>'); } 10.56%, 27.21% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="22" y="22" width="56" height="56" fill="none" stroke="%23FCEE0A" stroke-width="8" stroke-linejoin="round"/></svg>'); } 27.22%, 43.88% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,10 88,38 74,82 26,82 12,38" fill="none" stroke="%23FCEE0A" stroke-width="8" stroke-linejoin="round"/></svg>'); } 43.89%, 60.55% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,10 85,30 85,70 50,90 15,70 15,30" fill="none" stroke="%23FCEE0A" stroke-width="8" stroke-linejoin="round"/></svg>'); } 60.56%, 77.21% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="35,10 65,10 90,35 90,65 65,90 35,90 10,65 10,35" fill="none" stroke="%23FCEE0A" stroke-width="8" stroke-linejoin="round"/></svg>'); } 77.22%, 93.88% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="36" fill="none" stroke="%23FCEE0A" stroke-width="8"/></svg>'); } 93.89%, 100% { background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,10 85,70 15,70" fill="none" stroke="%23FCEE0A" stroke-width="8" stroke-linejoin="round"/></svg>'); } }
    @keyframes customRotate { 0%, 25% { transform: rotate(0deg); animation-timing-function: cubic-bezier(0.75, 0, 0.25, 1); } 100% { transform: rotate(360deg); } }
    @keyframes loadingDots { 0%, 24.9% { content: "LOADING"; } 25%, 49.9% { content: "LOADING."; } 50%, 74.9% { content: "LOADING.."; } 75%, 100% { content: "LOADING..."; } }
    div[data-testid="stSpinner"] > div { display: none !important; }
    div[data-testid="stSpinner"] { display: flex; align-items: center; gap: 15px; }
    div[data-testid="stSpinner"]::before { content: ""; display: inline-block; width: 30px; height: 30px; background-size: contain; background-repeat: no-repeat; background-position: center; animation: shapeJump 9s infinite, customRotate 1.5s infinite; }
    div[data-testid="stSpinner"]::after { content: "LOADING"; color: #FCEE0A; font-weight: bold; letter-spacing: 2px; font-size: 16px; animation: loadingDots 6s infinite; }
</style>
"""

# ==========================================
# HELPER FUNCTIONS (Clean Architecture)
# ==========================================
def parse_decklist(decklist_text: str, cut_basic_lands: bool = False) -> Dict[str, Any]:
    """Parst die Deckliste in ein Dictionary."""
    deck_dict = {}
    basic_lands = {"forest", "mountain", "plains", "island", "swamp", "snow-covered forest", "snow-covered mountain", "snow-covered plains", "snow-covered island", "snow-covered swamp"}
    
    for line in decklist_text.strip().split('\n'):
        line = line.strip()
        if not line or re.match(r'^(sideboard|commander|maybeboard|mainboard|companion)', line, re.IGNORECASE):
            continue
            
        count_match = re.match(r'^(\d+)[xX]?\s+(.+)$', line)
        count = int(count_match.group(1)) if count_match else 1
        rest = count_match.group(2).strip() if count_match else line
            
        set_code, cn = "", ""
        match = re.search(r'[\(\[]([^)\]]+)[\)\]]\s*([a-zA-Z0-9★_]+)?$', rest)
        if match:
            set_code = match.group(1).lower()
            cn = match.group(2) if match.group(2) else ""
            rest = rest[:match.start()].strip()
            
        name = rest.split('(')[0].replace('*', '').split(' / ')[0].split(' // ')[0].strip()
        
        if cut_basic_lands and name.lower() in basic_lands:
            continue
        
        key = f"{name}|{set_code}|{cn}"
        if key in deck_dict:
            deck_dict[key]['count'] += count
        else:
            deck_dict[key] = {'name': name, 'set': set_code, 'cn': cn, 'count': count}
            
    return deck_dict

def sort_preview_cards(cards: List[Dict]) -> None:
    """Sortiert Karten sauber nach Typ für das UI Layout."""
    def sort_key(c):
        main_type = c['type'].split('—')[0].lower()
        if 'basic land' in main_type: return 90
        elif 'land' in main_type: return 80
        elif 'creature' in main_type: return 10
        elif 'planeswalker' in main_type: return 20
        elif 'artifact' in main_type: return 30
        elif 'enchantment' in main_type: return 40
        elif 'instant' in main_type or 'sorcery' in main_type: return 50
        else: return 60
    if cards:
        cards.sort(key=sort_key)

# ==========================================
# API & IMAGE PROCESSING LOGIC
# ==========================================
def build_cascade_steps(art_style: str, set_code_global: str, lang: str, fancy_mode: bool) -> List[Dict[str, str]]:
    """Generiert intelligente, priorisierte Scryfall-Such-Schritte."""
    steps = []
    art_map = {"Borderless": "is:borderless", "Showcase": "is:showcase", "Retro": "is:retro", "Extended Art": "is:extendedart"}
    fancy_query = "(is:showcase OR is:borderless OR is:extendedart OR frame:extendedart)"
    
    # 1. Custom Style + Set
    if art_style != "Standard" and art_style in art_map:
        step = {'style': art_map[art_style]}
        if set_code_global: step['set'] = set_code_global
        if lang != 'en': step['lang'] = lang
        steps.append(step)
    
    # 2. Fancy Mode (True Premium versions) + Set
    if fancy_mode:
        step = {'style': fancy_query}
        if set_code_global: step['set'] = set_code_global
        if lang != 'en': step['lang'] = lang
        steps.append(step)
        
    # 3. Set fallback
    if set_code_global:
        steps.append({'set': set_code_global, 'lang': lang if lang != 'en' else None})
        
    # 4. Language fallback
    if lang != 'en':
        steps.append({'lang': lang})
        
    # 5. Ultimate fallback (just find the card)
    steps.append({})
    return steps

def get_card_data_smart_cascade(deck_dict: Dict, progress_bar, status_text, lang: str, art_style: str, set_code_global: str, fancy_mode: bool):
    """Holt die Karten-Daten intelligent und effizient aus Scryfall."""
    headers = {'User-Agent': 'Proxyfy/Smart-Cascade', 'Accept': 'application/json'}
    fetched_cards = {}
    error_log = {}
    
    remaining_keys = list(deck_dict.keys())
    cascade_steps = build_cascade_steps(art_style, set_code_global, lang, fancy_mode)
    
    total_steps = len(cascade_steps)
    
    for step_idx, step_filters in enumerate(cascade_steps, 1):
        if not remaining_keys: break
            
        status_text.text(f"Querying Scryfall step {step_idx}/{total_steps} ({len(remaining_keys)} cards remaining)...")
        chunks = [remaining_keys[i:i + 15] for i in range(0, len(remaining_keys), 15)]
        still_missing = []
        
        for chunk in chunks:
            or_terms = []
            for key in chunk:
                info = deck_dict[key]
                safe_name = info['name'].replace('"', '')
                term = f'!"{safe_name}"'
                if info['set']: term += f" e:{info['set']}"
                if info['cn']: term += f" cn:{info['cn']}"
                or_terms.append(f"({term})")
                
            q = f"({ ' OR '.join(or_terms) })"
            
            global_filters = []
            if step_filters.get('style'): global_filters.append(step_filters['style'])
            if step_filters.get('set'): global_filters.append(f"e:{step_filters['set']}")
            if step_filters.get('lang'): global_filters.append(f"lang:{step_filters['lang']}")
                
            if global_filters: q = f"{q} " + " ".join(global_filters)
            q += " include:extras"
                
            time.sleep(0.1) # Leicht reduziert für besseren Flow
            try:
                response = requests.get("https://api.scryfall.com/cards/search", params={'q': q}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    available_cards = list(data.get('data', []))
                    found_in_batch = set()
                    
                    for key in chunk:
                        if key in found_in_batch: continue
                        info = deck_dict[key]
                        orig_lower = info['name'].lower()
                        best_match_idx = -1
                        
                        for idx, card in enumerate(available_cards):
                            valid_names = set()
                            for k in ['name', 'flavor_name', 'printed_name']:
                                if card.get(k): valid_names.add(str(card[k]).lower())
                            for face in card.get('card_faces', []):
                                for k in ['name', 'flavor_name', 'printed_name']:
                                    if face.get(k): valid_names.add(str(face[k]).lower())
                            for n in list(valid_names):
                                valid_names.update([s.strip() for s in n.split('//')])
                                
                            if orig_lower in valid_names:
                                if info['set'] == str(card.get('set', '')).lower() and info['cn'] == str(card.get('collector_number', '')).lower():
                                    best_match_idx = idx
                                    break
                                elif best_match_idx == -1:
                                    best_match_idx = idx
                                    
                        if best_match_idx != -1:
                            fetched_cards[key] = available_cards.pop(best_match_idx)
                            found_in_batch.add(key)
                                
                    for key in chunk:
                        if key not in found_in_batch: still_missing.append(key)
                else:
                    still_missing.extend(chunk)
            except Exception:
                still_missing.extend(chunk)
                
        remaining_keys = list(dict.fromkeys(still_missing))
        
    for key in remaining_keys:
        error_log[deck_dict[key]['name']] = "Card or Token not found"
    
    card_metadata = []
    for key, info in deck_dict.items():
        if key in fetched_cards:
            card_data = fetched_cards[key]
            type_line = card_data.get('type_line', '')
            colors = card_data.get('colors') or (card_data.get('card_faces', [{}])[0].get('colors', []))
                
            img_urls = []
            if 'image_uris' in card_data:
                img_urls.append(card_data['image_uris'].get('png', card_data['image_uris'].get('large')))
            elif 'card_faces' in card_data:
                for face in card_data['card_faces']:
                    face_url = face.get('image_uris', {}).get('png', face.get('image_uris', {}).get('large'))
                    if face_url: img_urls.append(face_url)
                        
            if img_urls:
                card_metadata.append({'name': info['name'], 'urls': img_urls, 'type': type_line, 'colors': colors, 'count': info['count']})
                
    progress_bar.progress(1.0)
    return card_metadata, error_log

def download_image(url, corner_style):
    headers = {'User-Agent': 'Proxyfy/Pro-Downloader'}
    img_response = requests.get(url, headers=headers)
    img = Image.open(BytesIO(img_response.content)).convert("RGBA")
    
    if corner_style == "Rounded":
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=int(img.size[0] * 0.045), fill=255)
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=mask)
        return background
    else:
        background = Image.new("RGB", img.size, (0, 0, 0)) 
        background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
        return background

def generate_deck_pdf(card_metadata, output_filename, paper_size_tuple, corner_style, spacing):
    progress_bar = st.progress(0)
    c = canvas.Canvas(output_filename, pagesize=paper_size_tuple)
    page_width, page_height = paper_size_tuple
    
    current_margin_x = 0 if spacing == 0 else MARGIN_X
    current_margin_y = 0 if spacing == 0 else MARGIN_Y
    x_start = current_margin_x
    y_start = page_height - current_margin_y - CARD_HEIGHT
    
    max_cols = int((page_width - 2 * current_margin_x + spacing) // (CARD_WIDTH + spacing))
    max_rows = int((page_height - 2 * current_margin_y + spacing) // (CARD_HEIGHT + spacing))
    
    col, row, images_added, downloaded = 0, 0, 0, 0
    total_downloads = sum(len(item['urls']) for item in card_metadata)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in card_metadata:
            future_to_url = {executor.submit(download_image, url, corner_style): url for url in item['urls']}
            downloaded_images = []
            
            for future in concurrent.futures.as_completed(future_to_url):
                try: downloaded_images.append(future.result())
                except Exception: pass
                downloaded += 1
                if total_downloads > 0: progress_bar.progress(downloaded / total_downloads)
                
            for _ in range(item['count']):
                for img in downloaded_images:
                    x = x_start + col * (CARD_WIDTH + spacing)
                    y = y_start - row * (CARD_HEIGHT + spacing)
                    c.drawImage(ImageReader(img), x, y, width=CARD_WIDTH, height=CARD_HEIGHT)
                    images_added += 1
                    
                    col += 1
                    if col >= max_cols:
                        col, row = 0, row + 1
                    if row >= max_rows:
                        c.showPage()
                        col, row = 0, 0

    if images_added > 0: c.save()
    return images_added

def generate_deck_jpgs(card_metadata, corner_style, spacing, white_bg=True):
    progress_bar = st.progress(0)
    dpi = 300
    w_px, h_px = int((12.7 / 2.54) * dpi), int((17.8 / 2.54) * dpi)
    card_w_px, card_h_px = int((63 / 25.4) * dpi), int((88 / 25.4) * dpi)
    spacing_px = int((spacing / mm) / 25.4 * dpi)
    
    margin_x_px = max(0, (w_px - (2 * card_w_px + spacing_px)) // 2)
    margin_y_px = max(0, (h_px - (2 * card_h_px + spacing_px)) // 2)
    bg_color = (255, 255, 255) if white_bg else (0, 0, 0)
    
    jpg_pages = []
    current_page_img = Image.new("RGB", (w_px, h_px), bg_color)
    col, row, images_added, downloaded = 0, 0, 0, 0
    total_downloads = sum(len(item['urls']) for item in card_metadata)
    
    flat_card_images = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in card_metadata:
            future_to_url = {executor.submit(download_image, url, corner_style): url for url in item['urls']}
            downloaded_images = []
            for future in concurrent.futures.as_completed(future_to_url):
                try: downloaded_images.append(future.result())
                except: pass
                downloaded += 1
                if total_downloads > 0: progress_bar.progress(downloaded / total_downloads)
            
            for _ in range(item['count']):
                for img in downloaded_images:
                    flat_card_images.append(img.resize((card_w_px, card_h_px), Image.Resampling.LANCZOS))

    for img in flat_card_images:
        x = margin_x_px + col * (card_w_px + spacing_px)
        y = margin_y_px + row * (card_h_px + spacing_px)
        current_page_img.paste(img, (x, y))
        images_added += 1
        col += 1
        
        if col >= 2: col, row = 0, row + 1
        if row >= 2:
            jpg_pages.append(current_page_img)
            current_page_img = Image.new("RGB", (w_px, h_px), bg_color)
            col, row = 0, 0
            
    if col > 0 or row > 0: jpg_pages.append(current_page_img)
    progress_bar.empty()
    return jpg_pages


# ==========================================
# STREAMLIT USER INTERFACE & SESSION STATE
# ==========================================
st.set_page_config(page_title="Proxyfy by Nefpo", layout="wide")
st.markdown(CSS_STYLES, unsafe_allow_html=True)
st.markdown('<div id="top"></div>', unsafe_allow_html=True)

# V3.0: SCROLL MEMORY MANAGEMENT
if 'scroll_target' not in st.session_state: st.session_state.scroll_target = None
if st.session_state.scroll_target:
    components.html(
        f"<script>window.parent.document.getElementById('{st.session_state.scroll_target}').scrollIntoView({{behavior: 'smooth', block: 'center'}});</script>",
        height=0
    )
    st.session_state.scroll_target = None

if 'preview_cards' not in st.session_state: st.session_state.preview_cards = None
if 'error_log' not in st.session_state: st.session_state.error_log = None
if 'output_ready' not in st.session_state: st.session_state.output_ready = False
if 'output_data' not in st.session_state: st.session_state.output_data = None
if 'output_filename' not in st.session_state: st.session_state.output_filename = None
if 'is_jpg_mode' not in st.session_state: st.session_state.is_jpg_mode = False
if 'images_added' not in st.session_state: st.session_state.images_added = 0
if 'editing_idx' not in st.session_state: st.session_state.editing_idx = None
if 'variants_data' not in st.session_state: st.session_state.variants_data = None
if 'file_size_mb' not in st.session_state: st.session_state.file_size_mb = None

st.title("Proxyfy by Nefpo")
st.write("Free print-ready proxies with lossless quality.")

with st.sidebar:
    st.header("Card & Art Settings")
    fancy_mode = st.checkbox("Fancy (Prioritize Premium/Full-Art)", value=False)
    cut_basic_lands = st.checkbox("Cut Basic Lands", value=False)
    lang_input = st.selectbox("Preferred Language", ["English (en)", "German (de)", "Japanese (ja)", "French (fr)", "Spanish (es)"])
    lang_code = lang_input.split("(")[1].replace(")", "")
    art_style = st.selectbox("Override Frame / Art Style", ["Standard", "Extended Art", "Borderless", "Showcase", "Retro"])
    set_code = st.text_input("Specific Set Code (Optional, e.g. 'mh2')", value="")
    
    st.markdown("---")
    st.header("Preview Settings")
    grid_size = st.slider("Preview Grid Columns", min_value=2, max_value=10, value=5)
    
    st.markdown("---")
    st.header("Print Settings")
    cut_mode = st.radio("Layout Mode", ["Guided Cut (0.25mm Ultra-Thin Hairlines)", "Normal Mode (2mm Spacing)", "Single Cut Mode (No Spacing)"])
    
    if "Guided" in cut_mode:
        actual_spacing = 0.25 * mm
        is_white_bg = True
    elif "Single" in cut_mode:
        actual_spacing = 0
        is_white_bg = True
    else:
        actual_spacing = 2 * mm
        is_white_bg = True
    
    corner_style = st.radio("Card Corners", ["Sharp (Square)", "Rounded"]) 
    paper_size_name = st.selectbox("Paper Size", ["Kaufland Foto (13x18 cm)", "A4", "A3", "US (Legal)", "DM Poster (20x30 cm)", "DM Foto (15x20 cm)"])
    
    paper_sizes = {
        "A4": A4, "A3": A3, "US (Legal)": legal,
        "DM Poster (20x30 cm)": (200 * mm, 300 * mm),
        "DM Foto (15x20 cm)": (150 * mm, 200 * mm),
        "Kaufland Foto (13x18 cm)": (127 * mm, 178 * mm)
    }
    selected_paper = paper_sizes[paper_size_name]

decklist_input = st.text_area("Paste your decklist here:", height=200)

if st.button("Load Cards & Show Preview", type="primary"):
    st.session_state.output_ready = False 
    st.session_state.output_data = None
    st.session_state.editing_idx = None
    st.session_state.file_size_mb = None
    
    if decklist_input.strip() == "":
        st.error("Please enter a decklist first.")
    else:
        deck_dict = parse_decklist(decklist_input, cut_basic_lands)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with st.spinner("Fetching card data from Scryfall..."):
            cards, errors = get_card_data_smart_cascade(deck_dict, progress_bar, status_text, lang_code, art_style, set_code.strip(), fancy_mode)
            sort_preview_cards(cards)
            
            st.session_state.preview_cards = cards
            st.session_state.error_log = errors
            
            progress_bar.empty()
            status_text.empty()

if st.session_state.preview_cards is not None:
    st.markdown("---")
    
    if st.session_state.editing_idx is not None:
        edit_idx = st.session_state.editing_idx
        active_card = st.session_state.preview_cards[edit_idx]
        
        st.subheader(f"Editing Artwork: {active_card['name']} ({active_card['count']} copies left to assign)")
        
        if st.button("Finish & Return to Deck", key="cancel_edit"):
            st.session_state.scroll_target = f"card_anchor_{edit_idx}"
            st.session_state.editing_idx = None
            st.session_state.variants_data = None
            sort_preview_cards(st.session_state.preview_cards)
            st.rerun()
            
        if st.session_state.variants_data is None:
            with st.spinner("Loading all available artworks..."):
                safe_name = active_card['name'].replace('"', '')
                res = requests.get("https://api.scryfall.com/cards/search", params={'q': f'!"{safe_name}" include:extras', 'unique': 'prints'}, headers={'Accept': 'application/json'})
                st.session_state.variants_data = res.json().get('data', []) if res.status_code == 200 else []
                    
        variants = st.session_state.variants_data
        if variants:
            for i in range(0, len(variants), grid_size):
                v_cols = st.columns(grid_size)
                for j in range(grid_size):
                    v_idx = i + j
                    if v_idx < len(variants):
                        v_card = variants[v_idx]
                        with v_cols[j]:
                            v_img_urls = []
                            if 'image_uris' in v_card: v_img_urls.append(v_card['image_uris'].get('png', v_card['image_uris'].get('large')))
                            elif 'card_faces' in v_card:
                                for face in v_card['card_faces']:
                                    f_url = face.get('image_uris', {}).get('png', face.get('image_uris', {}).get('large'))
                                    if f_url: v_img_urls.append(f_url)
                                    
                            if v_img_urls:
                                st.image(v_img_urls[0], use_container_width=True)
                                set_name, c_num = v_card.get('set', '').upper(), v_card.get('collector_number', '')
                                split_count = st.number_input("Copies", min_value=0, max_value=active_card['count'], value=0, step=1, label_visibility="collapsed", key=f"split_num_{v_idx}") if active_card['count'] > 1 else 1
                                
                                if st.button(f"Select {set_name} #{c_num}", key=f"sel_var_{v_idx}"):
                                    if split_count == 0: st.warning("Please select at least 1 copy using the '+' button above.")
                                    elif split_count < active_card['count']:
                                        leftover_card = copy.deepcopy(active_card)
                                        leftover_card['count'] -= split_count
                                        st.session_state.preview_cards[edit_idx]['count'] = split_count
                                        st.session_state.preview_cards[edit_idx]['urls'] = v_img_urls
                                        st.session_state.preview_cards.append(leftover_card)
                                        st.session_state.editing_idx = len(st.session_state.preview_cards) - 1
                                        st.session_state.output_ready = False 
                                        st.rerun()
                                    else:
                                        st.session_state.preview_cards[edit_idx]['urls'] = v_img_urls
                                        st.session_state.scroll_target = f"card_anchor_{edit_idx}"
                                        st.session_state.editing_idx = None
                                        st.session_state.variants_data = None
                                        st.session_state.output_ready = False 
                                        sort_preview_cards(st.session_state.preview_cards)
                                        st.rerun()
        else: st.warning("No other artworks found for this card.")
            
    else:
        st.subheader(f"Deck Preview ({sum(c['count'] for c in st.session_state.preview_cards)} Cards)")
        
        if st.session_state.error_log:
            st.warning("The following cards could not be found:")
            for card, err in st.session_state.error_log.items(): st.write(f"- {card}: {err}")
        
        grouped_cards = {}
        for global_idx, card in enumerate(st.session_state.preview_cards):
            main_type = card['type'].split('—')[0].strip().lower()
            if 'basic land' in main_type: group = "Basic Lands"
            elif 'land' in main_type: group = "Lands"
            elif 'creature' in main_type: group = "Creatures"
            elif 'planeswalker' in main_type: group = "Planeswalkers"
            elif 'artifact' in main_type: group = "Artifacts"
            elif 'enchantment' in main_type: group = "Enchantments"
            elif 'instant' in main_type: group = "Instants"
            elif 'sorcery' in main_type: group = "Sorceries"
            else: group = "Others"
            grouped_cards.setdefault(group, []).append((global_idx, card))
            
        group_order = ["Creatures", "Planeswalkers", "Artifacts", "Enchantments", "Instants", "Sorceries", "Others", "Lands", "Basic Lands"]
        
        for group_name in group_order:
            if group_name in grouped_cards:
                group_items = grouped_cards[group_name]
                st.markdown(f"<div class='group-title'>{group_name} ({sum(c['count'] for _, c in group_items)})</div>", unsafe_allow_html=True)
                
                with st.container():
                    st.markdown('<span class="card-group-marker"></span>', unsafe_allow_html=True)
                    for i in range(0, len(group_items), grid_size):
                        cols = st.columns(grid_size)
                        for j in range(grid_size):
                            if i + j < len(group_items):
                                global_idx, card = group_items[i + j]
                                with cols[j]:
                                    st.markdown(f'<div id="card_anchor_{global_idx}"></div><span class="card-grid-marker"></span>', unsafe_allow_html=True)
                                    st.image(card['urls'][0], use_container_width=True)
                                    st.markdown(f"""<div style="text-align: center; height: 2.8em; line-height: 1.4em; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; font-size: 14px; margin-bottom: 10px; color: #E0E0E0;" title="{card['count']}x {card['name']}">{card['count']}x {card['name']}</div>""", unsafe_allow_html=True)
                                    
                                    if st.button("Change Art", key=f"change_art_{global_idx}"):
                                        st.session_state.editing_idx = global_idx
                                        st.session_state.variants_data = None
                                        st.session_state.scroll_target = "top"
                                        st.rerun()
        
        st.markdown("---")
        if st.button("Generate Print-Ready Output", type="primary", use_container_width=True):
            if "Kaufland" in paper_size_name or "DM Foto" in paper_size_name:
                st.session_state.is_jpg_mode = True
                with st.spinner("Rendering High-Res JPGs (300 DPI) with Guided Alignment..."):
                    jpg_pages = generate_deck_jpgs(st.session_state.preview_cards, corner_style.split()[0], actual_spacing, white_bg=is_white_bg)
                    st.session_state.images_added = sum(c['count'] for c in st.session_state.preview_cards)
                    
                    if len(jpg_pages) == 1:
                        buf = BytesIO()
                        jpg_pages[0].save(buf, format="JPEG", quality=100)
                        st.session_state.output_data = buf.getvalue()
                        st.session_state.output_filename = "Proxyfy_Photo.jpg"
                    else:
                        import zipfile
                        zip_buf = BytesIO()
                        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for p_idx, p_img in enumerate(jpg_pages):
                                p_buf = BytesIO()
                                p_img.save(p_buf, format="JPEG", quality=100)
                                zip_file.writestr(f"Proxyfy_Photo_Page_{p_idx+1}.jpg", p_buf.getvalue())
                        st.session_state.output_data = zip_buf.getvalue()
                        st.session_state.output_filename = "Proxyfy_Photos.zip"
                        
                    st.session_state.output_ready = True
            else:
                st.session_state.is_jpg_mode = False
                pdf_filename = "Proxyfy_Deck.pdf"
                with st.spinner("Processing Card Images and building PDF..."):
                    images_added = generate_deck_pdf(st.session_state.preview_cards, pdf_filename, selected_paper, corner_style.split()[0], actual_spacing)
                
                if images_added > 0 and os.path.exists(pdf_filename):
                    st.session_state.file_size_mb = os.path.getsize(pdf_filename) / (1024 * 1024)
                    st.session_state.images_added = images_added
                    with open(pdf_filename, "rb") as pdf_file:
                        st.session_state.output_data = pdf_file.read()
                        st.session_state.output_filename = "Proxyfy_Deck.pdf"
                        st.session_state.output_ready = True
                    
        if st.session_state.output_ready and st.session_state.output_data is not None:
            if st.session_state.is_jpg_mode:
                st.success(f"Success: {st.session_state.images_added} cards generated for Photo Print.")
                st.download_button(label="Download Photos (ZIP)" if "zip" in st.session_state.output_filename else "Download Photo (JPG)", data=st.session_state.output_data, file_name=st.session_state.output_filename, mime="application/zip" if "zip" in st.session_state.output_filename else "image/jpeg", use_container_width=True)
            else:
                size_text = f"{st.session_state.file_size_mb:.2f} MB" if st.session_state.file_size_mb else ""
                st.success(f"Success: {st.session_state.images_added} cards generated on {paper_size_name} paper. ({size_text})")
                st.download_button(label=f"Download PDF ({size_text})" if size_text else "Download PDF", data=st.session_state.output_data, file_name=st.session_state.output_filename, mime="application/pdf", use_container_width=True)

st.markdown('<a href="#top" target="_self" class="tp-to-top-btn">TP TO THE TOP</a>', unsafe_allow_html=True)
