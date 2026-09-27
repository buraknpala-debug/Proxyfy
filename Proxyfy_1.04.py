import streamlit as st
import os
import re
import time
import requests
import concurrent.futures
from io import BytesIO
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, legal
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

# --- Configuration ---
CARD_WIDTH = 63 * mm
CARD_HEIGHT = 88 * mm
MARGIN_X = 5 * mm
MARGIN_Y = 5 * mm
SPACING = 2 * mm 

def parse_decklist(decklist_text, cut_basic_lands=False):
    deck_dict = {}
    basic_lands = {
        "forest", "mountain", "plains", "island", "swamp", 
        "snow-covered forest", "snow-covered mountain", 
        "snow-covered plains", "snow-covered island", "snow-covered swamp"
    }
    
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
            
        set_code = ""
        cn = ""
        match = re.search(r'\(([^)]+)\)\s*([a-zA-Z0-9★_]+)?$', rest)
        if match:
            set_code = match.group(1).lower()
            cn = match.group(2) if match.group(2) else ""
            name = rest[:match.start()].strip()
        else:
            name = rest
            
        if '(' in name: name = name.split('(')[0].strip()
        if '*' in name: name = name.replace('*', '').strip()
        name = name.split(' / ')[0].split(' // ')[0].strip()
        
        if cut_basic_lands and name.lower() in basic_lands:
            continue
        
        key = f"{name}|{set_code}|{cn}"
        
        if key in deck_dict:
            deck_dict[key]['count'] += count
        else:
            deck_dict[key] = {
                'name': name,
                'set': set_code,
                'cn': cn,
                'count': count
            }
        
    return deck_dict

def get_card_data_smart_cascade(deck_dict, progress_bar, status_text, lang, art_style, set_code_global, fancy_mode):
    headers = {'User-Agent': 'Proxyfy/Smart-Cascade', 'Accept': 'application/json'}
    fetched_cards = {}
    error_log = {}
    
    remaining_keys = list(deck_dict.keys())
    
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
    if set_code_global: 
        step_custom['set'] = set_code_global
    if lang != 'en': 
        step_custom['lang'] = lang
    if step_custom:
        cascade_steps.append(step_custom)
        
    if art_style != "Standard" and art_style in art_map and set_code_global:
        cascade_steps.append({'style': art_map[art_style], 'lang': lang if lang != 'en' else None})
        
    if set_code_global:
        cascade_steps.append({'set': set_code_global, 'lang': lang if lang != 'en' else None})
        
    if lang != 'en':
        cascade_steps.append({'lang': lang})
        
    cascade_steps.append({})
    
    current_step = 1
    total_steps = len(cascade_steps) + (1 if fancy_mode else 0)
    
    if fancy_mode:
        status_text.text("Scanning card data for Fancy Mode (rarest/highest value arts)...")
        still_missing = []
        chunks = [remaining_keys[i:i + 15] for i in range(0, len(remaining_keys), 15)]
        
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
            if set_code_global: q = f"{q} e:{set_code_global}"
            q += " include:extras"
            
            time.sleep(0.15)
            try:
                # FIX: unique:prints ist jetzt ein API-Parameter, nicht Teil des Suchstrings
                response = requests.get("https://api.scryfall.com/cards/search", params={'q': q, 'unique': 'prints'}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    for key in chunk:
                        info = deck_dict[key]
                        orig_lower = info['name'].lower()
                        matching_prints = []
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
                            fetched_cards[key] = matching_prints[0]
                        else:
                            still_missing.append(key)
                else:
                    still_missing.extend(chunk)
            except:
                still_missing.extend(chunk)
        remaining_keys = list(dict.fromkeys(still_missing))
        current_step += 1

    for step_filters in cascade_steps:
        if not remaining_keys:
            break
            
        status_text.text(f"Querying Scryfall cascade step {current_step}/{total_steps} ({len(remaining_keys)} cards remaining)...")
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
            if 'style' in step_filters and step_filters['style']:
                global_filters.append(step_filters['style'])
            if 'set' in step_filters and step_filters['set']:
                global_filters.append(f"e:{step_filters['set']}")
            if 'lang' in step_filters and step_filters['lang']:
                global_filters.append(f"lang:{step_filters['lang']}")
                
            if global_filters:
                q = f"{q} " + " ".join(global_filters)
                
            q += " include:extras"
                
            time.sleep(0.15)
            try:
                response = requests.get("https://api.scryfall.com/cards/search", params={'q': q}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    available_cards = list(data.get('data', []))
                    found_in_batch = set()
                    
                    for key in chunk:
                        if key in found_in_batch:
                            continue
                        info = deck_dict[key]
                        orig_lower = info['name'].lower()
                        best_match_idx = -1
                        for idx, card in enumerate(available_cards):
                            card_name = card['name'].lower()
                            faces = [f.strip() for f in card_name.split('//')]
                            if orig_lower == card_name or orig_lower in faces:
                                if info['set'] == str(card.get('set', '')).lower() and info['cn'] == str(card.get('collector_number', '')).lower():
                                    best_match_idx = idx
                                    break
                                elif best_match_idx == -1:
                                    best_match_idx = idx
                                    
                        if best_match_idx != -1:
                            fetched_cards[key] = available_cards.pop(best_match_idx)
                            found_in_batch.add(key)
                                
                    for key in chunk:
                        if key not in found_in_batch:
                            still_missing.append(key)
                else:
                    still_missing.extend(chunk)
            except Exception:
                still_missing.extend(chunk)
                
        remaining_keys = list(dict.fromkeys(still_missing))
        current_step += 1
        
    for key in remaining_keys:
        error_log[deck_dict[key]['name']] = "Card or Token not found"
    
    card_metadata = []
    for key, info in deck_dict.items():
        if key in fetched_cards:
            card_data = fetched_cards[key]
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
                    'name': info['name'],
                    'urls': img_urls,
                    'type': type_line,
                    'colors': colors,
                    'count': info['count']
                })
                
    progress_bar.progress(1.0)
    return card_metadata, error_log

def download_image(url, corner_style):
    headers = {'User-Agent': 'Proxyfy/Smart-Cascade'}
    img_response = requests.get(url, headers=headers)
    img = Image.open(BytesIO(img_response.content)).convert("RGBA")
    
    if corner_style == "Rounded":
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        corner_radius = int(img.size[0] * 0.045)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=corner_radius, fill=255)
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=mask)
        return background
    else:
        background = Image.new("RGB", img.size, (0, 0, 0)) 
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        return background

def generate_deck_pdf(card_metadata, output_filename, paper_size_tuple, corner_style):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("Processing card images and building PDF...")
    progress_bar.progress(0.0)
    
    c = canvas.Canvas(output_filename, pagesize=paper_size_tuple)
    page_width, page_height = paper_size_tuple
    
    x_start = MARGIN_X
    y_start = page_height - MARGIN_Y - CARD_HEIGHT
    max_cols = int((page_width - 2 * MARGIN_X + SPACING) // (CARD_WIDTH + SPACING))
    max_rows = int((page_height - 2 * MARGIN_Y + SPACING) // (CARD_HEIGHT + SPACING))
    
    col = 0
    row = 0
    images_added = 0
    total_downloads = sum(len(item['urls']) for item in card_metadata)
    downloaded = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in card_metadata:
            future_to_url = {executor.submit(download_image, url, corner_style): url for url in item['urls']}
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
                    if col >= max_cols:
                        col = 0
                        row += 1
                        
                    if row >= max_rows:
                        c.showPage()
                        col = 0
                        row = 0

    if images_added > 0:
        c.save()
        status_text.text("PDF generated successfully.")
        
    return images_added

# ==========================================
# STREAMLIT USER INTERFACE & SESSION STATE
# ==========================================

st.set_page_config(page_title="Proxyfy Beta by Nefpo", layout="wide")

st.markdown("""
<style>
    div[data-baseweb="select"] > div, 
    div[data-baseweb="input"] > div,
    textarea {
        border-radius: 0px !important;
        border: 1px solid #333333 !important;
    }
    
    div[data-baseweb="select"] > div:focus-within, 
    div[data-baseweb="input"] > div:focus-within,
    textarea:focus {
        border: 1px solid #FCEE0A !important;
        box-shadow: 0 0 4px #FCEE0A40 !important;
    }

    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: transparent !important;
        color: #FCEE0A !important;
        border: 2px solid #FCEE0A !important;
        border-radius: 0px !important;
        text-transform: uppercase;
        font-weight: bold;
        letter-spacing: 2px;
        box-shadow: 0 0 3px #FCEE0A30;
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background-color: #FCEE0A !important;
        color: #000000 !important;
        box-shadow: 0 0 8px #FCEE0A, 0 0 15px #FCEE0A60 !important;
    }

    div[data-testid="stButton"] > button[kind="secondary"] {
        background-color: transparent !important;
        color: #E0E0E0 !important;
        border: 1px solid #444444 !important;
        border-radius: 0px !important;
        transition: all 0.2s ease-in-out;
        padding: 2px 10px;
        width: 100%;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        border: 1px solid #FCEE0A !important;
        color: #FCEE0A !important;
        box-shadow: 0 0 5px #FCEE0A40 !important;
    }

    img {
        border-radius: 0px !important;
        border: 1px solid #222222;
        transition: all 0.2s;
    }
    img:hover {
        border: 1px solid #FCEE0A;
        box-shadow: 0 0 6px #FCEE0A40;
        transform: scale(1.01);
    }
    
    .stProgress > div > div > div > div {
        background-color: #FCEE0A !important;
        box-shadow: 0 0 8px #FCEE0A !important;
    }
</style>
""", unsafe_allow_html=True)

if 'preview_cards' not in st.session_state:
    st.session_state.preview_cards = None
if 'error_log' not in st.session_state:
    st.session_state.error_log = None
if 'pdf_ready' not in st.session_state:
    st.session_state.pdf_ready = False
if 'pdf_data' not in st.session_state:
    st.session_state.pdf_data = None
if 'images_added' not in st.session_state:
    st.session_state.images_added = 0
if 'editing_idx' not in st.session_state:
    st.session_state.editing_idx = None
if 'variants_data' not in st.session_state:
    st.session_state.variants_data = None

st.title("Proxyfy Beta by Nefpo")
st.write("Generate print-ready PDFs with lossless PNG quality.")

with st.sidebar:
    st.header("Card & Art Settings")
    fancy_mode = st.checkbox("Fancy (Highest Value Artwork)", value=False)
    cut_basic_lands = st.checkbox("Cut Basic Lands", value=False)
    lang_input = st.selectbox("Preferred Language", ["English (en)", "German (de)", "Japanese (ja)", "French (fr)", "Spanish (es)"])
    lang_code = lang_input.split("(")[1].replace(")", "")
    art_style = st.selectbox("Override Frame / Art Style", ["Standard", "Extended Art", "Borderless", "Showcase", "Retro"])
    set_code = st.text_input("Specific Set Code (Optional, e.g. 'mh2')", value="")
    
    st.markdown("---")
    st.header("Print Settings")
    corner_style = st.radio("Card Corners", ["Sharp (Square)", "Rounded"]) 
    paper_size_name = st.selectbox("Paper Size", ["A4", "A3", "US (Legal)"])
    
    paper_sizes = {"A4": A4, "A3": A3, "US (Legal)": legal}
    selected_paper = paper_sizes[paper_size_name]

decklist_input = st.text_area("Paste your decklist here:", height=200)

if st.button("Load Cards & Show Preview", type="primary"):
    st.session_state.pdf_ready = False 
    st.session_state.pdf_data = None
    st.session_state.editing_idx = None
    
    if decklist_input.strip() == "":
        st.error("Please enter a decklist first.")
    else:
        deck_dict = parse_decklist(decklist_input, cut_basic_lands)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with st.spinner("Fetching card data from Scryfall..."):
            cards, errors = get_card_data_smart_cascade(deck_dict, progress_bar, status_text, lang_code, art_style, set_code.strip(), fancy_mode)
            
            def sort_key(c):
                main_type = c['type'].split('—')[0].lower()
                num_colors = len(c['colors'])
                if 'basic land' in main_type: return 90
                elif 'land' in main_type: return 80
                elif 'creature' in main_type:
                    return 10 - num_colors if num_colors > 1 else (15 if num_colors == 1 else 20)
                elif 'planeswalker' in main_type: return 30
                elif 'instant' in main_type or 'sorcery' in main_type: return 40
                elif 'enchantment' in main_type: return 50
                elif 'artifact' in main_type: return 60
                else: return 70
                
            if cards:
                cards.sort(key=sort_key)
            
            st.session_state.preview_cards = cards
            st.session_state.error_log = errors
            
            progress_bar.empty()
            status_text.empty()

if st.session_state.preview_cards is not None:
    st.markdown("---")
    
    if st.session_state.editing_idx is not None:
        edit_idx = st.session_state.editing_idx
        active_card = st.session_state.preview_cards[edit_idx]
        
        st.subheader(f"Editing Artwork: {active_card['name']}")
        if st.button("Cancel & Return to Deck", key="cancel_edit"):
            st.session_state.editing_idx = None
            st.session_state.variants_data = None
            st.rerun()
            
        if st.session_state.variants_data is None:
            with st.spinner("Loading all available artworks..."):
                safe_name = active_card['name'].replace('"', '')
                q = f'!"{safe_name}" include:extras'
                # FIX: unique:prints ist jetzt sauber als Parameter getrennt
                res = requests.get("https://api.scryfall.com/cards/search", params={'q': q, 'unique': 'prints'}, headers={'User-Agent': 'Proxyfy/Smart-Cascade', 'Accept': 'application/json'})
                if res.status_code == 200:
                    st.session_state.variants_data = res.json().get('data', [])
                else:
                    st.session_state.variants_data = []
                    
        variants = st.session_state.variants_data
        if variants:
            v_cols = st.columns(5)
            for v_idx, v_card in enumerate(variants):
                with v_cols[v_idx % 5]:
                    v_img_urls = []
                    if 'image_uris' in v_card:
                        v_img_urls.append(v_card['image_uris'].get('png', v_card['image_uris'].get('large')))
                    elif 'card_faces' in v_card:
                        for face in v_card['card_faces']:
                            f_url = face.get('image_uris', {}).get('png', face.get('image_uris', {}).get('large'))
                            if f_url: v_img_urls.append(f_url)
                            
                    if v_img_urls:
                        st.image(v_img_urls[0], use_container_width=True)
                        set_name = v_card.get('set', '').upper()
                        c_num = v_card.get('collector_number', '')
                        
                        if st.button(f"Select {set_name} #{c_num}", key=f"sel_var_{v_idx}"):
                            st.session_state.preview_cards[edit_idx]['urls'] = v_img_urls
                            st.session_state.editing_idx = None
                            st.session_state.variants_data = None
                            st.session_state.pdf_ready = False 
                            st.rerun()
        else:
            st.warning("No other artworks found for this card.")
            
    else:
        st.subheader(f"Deck Preview ({sum(c['count'] for c in st.session_state.preview_cards)} Cards)")
        
        if st.session_state.error_log:
            st.warning("The following cards could not be found:")
            for card, err in st.session_state.error_log.items():
                st.write(f"- {card}: {err}")
        
        cols = st.columns(5)
        for idx, card in enumerate(st.session_state.preview_cards):
            with cols[idx % 5]:
                st.image(card['urls'][0], caption=f"{card['count']}x {card['name']}", use_container_width=True)
                if st.button("Change Art", key=f"change_art_{idx}"):
                    st.session_state.editing_idx = idx
                    st.session_state.variants_data = None
                    st.rerun()
        
        st.markdown("---")
        
        if st.button("Generate Print-Ready PDF", type="primary", use_container_width=True):
            pdf_filename = "Proxyfy_Deck.pdf"
            images_added = generate_deck_pdf(st.session_state.preview_cards, pdf_filename, selected_paper, corner_style.split()[0])
            
            if images_added > 0 and os.path.exists(pdf_filename):
                with open(pdf_filename, "rb") as pdf_file:
                    st.session_state.pdf_data = pdf_file.read()
                    st.session_state.pdf_ready = True
                    st.session_state.images_added = images_added
                
                try:
                    webhook_url = "DEINE_MAKE_COM_WEBHOOK_URL_HIER_EINTRAGEN"
                    payload = {
                        "event": "pdf_generated",
                        "cards_total": images_added,
                        "fancy_mode": fancy_mode,
                        "lang": lang_code,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    requests.post(webhook_url, json=payload, timeout=2)
                except Exception:
                    pass
                    
        if st.session_state.pdf_ready and st.session_state.pdf_data is not None:
            st.success(f"Success: {st.session_state.images_added} cards generated on {paper_size_name} paper with {corner_style.lower()} corners.")
            st.download_button(
                label="Download PDF",
                data=st.session_state.pdf_data,
                file_name="Proxyfy_Deck.pdf",
                mime="application/pdf",
                use_container_width=True
            )
