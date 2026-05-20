import streamlit as st
import fitz
import io
from PIL import Image

st.set_page_config(page_title="Rimuovi Immagini e Testi dal PDF", layout="wide")
st.title("Rimuovi Immagini e Testi dal PDF")
st.write("Carica il PDF. Seleziona le immagini o i testi da eliminare e procedi con la rimozione.")

# --- FUNZIONI DI CALLBACK PER I PULSANTI SELEZIONA/DESELEZIONA TUTTE ---
def select_all_images():
    for img in st.session_state.get('images_found', []):
        st.session_state[img["id"]] = True

def deselect_all_images():
    for img in st.session_state.get('images_found', []):
        st.session_state[img["id"]] = False

# --- CARICAMENTO FILE ---
uploaded_file = st.file_uploader("Carica il file PDF", type="pdf")

if uploaded_file is not None:
    # Inizializzazione delle variabili di sessione quando viene caricato un nuovo file
    if 'pdf_bytes' not in st.session_state or st.session_state.get('file_name') != uploaded_file.name:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.file_name = uploaded_file.name
        st.session_state.search_results = []
        st.session_state.images_found = []
        st.session_state.needs_extraction = True # Flag per forzare l'estrazione immagini iniziale
    
    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
    
    # --- ESTRAZIONE AUTOMATICA DELLE IMMAGINI ---
    if st.session_state.get('needs_extraction', False):
        images_found = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0] 
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    image = Image.open(io.BytesIO(image_bytes))
                    image.thumbnail((200, 200))
                    
                    images_found.append({
                        "id": f"img_p{page_num}_{xref}_{img_index}",
                        "type": "image",
                        "xref": xref,
                        "page": page_num,
                        "preview": image
                    })
                except Exception:
                    continue 
                    
        st.session_state.images_found = images_found
        st.session_state.needs_extraction = False # Estrazione completata, non ripeterla finché non si modifica il PDF

    # --- CALCOLO IN TEMPO REALE DELLE SELEZIONI ---
    # Legge direttamente dallo stato delle checkbox (tramite il "key") per sapere cosa è spuntato
    texts_to_delete = [res for res in st.session_state.get('search_results', []) if st.session_state.get(res["id"], False)]
    images_to_delete = [img for img in st.session_state.get('images_found', []) if st.session_state.get(img["id"], False)]
    total_selections = len(texts_to_delete) + len(images_to_delete)

    # --- BARRA SUPERIORE: INFO, DOWNLOAD E RIMOZIONE ---
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"PDF in lavorazione: {doc.page_count} pagine.")
    with col2:
        st.download_button(
            label="Scarica documento attuale",
            data=st.session_state.pdf_bytes,
            file_name=f"Modificato_{st.session_state.file_name}",
            mime="application/pdf",
            use_container_width=True
        )

    st.markdown("---")
    
    # Il pulsante di rimozione è ora in cima e sempre visibile
    if st.button(f"🚀 Rimuovi Selezionati ({total_selections})", disabled=total_selections==0, type="primary", use_container_width=True):
        with st.spinner("Modifica del PDF in corso..."):
            
            # 1. Rimuovi i testi
            pages_to_redact = set()
            for res in texts_to_delete:
                page = doc[res["page"]]
                page.add_redact_annot(res["rect"])
                pages_to_redact.add(res["page"])
                
            for page_num in pages_to_redact:
                page = doc[page_num]
                page.apply_redactions(images=0)
                
            # 2. Rimuovi le immagini
            for res in images_to_delete:
                xref = res["xref"]
                doc.xref_set_key(xref, "Subtype", "/Form")
                doc.xref_set_key(xref, "BBox", "[0 0 0 0]")
                doc.xref_set_key(xref, "Width", "null")
                doc.xref_set_key(xref, "Height", "null")
                doc.xref_set_key(xref, "ColorSpace", "null")
                doc.xref_set_key(xref, "Filter", "null")
                doc.update_stream(xref, b"")
            
            # 3. Salva e aggiorna
            out_pdf = io.BytesIO()
            doc.save(out_pdf, garbage=4, deflate=True)
            
            st.session_state.pdf_bytes = out_pdf.getvalue()
            st.session_state.search_results = []
            st.session_state.needs_extraction = True # Forza la ricerca delle immagini aggiornate
            
            # Pulisce le vecchie selezioni per evitare "spunte fantasma" sul nuovo PDF
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith("img_p") or k.startswith("text_p")]
            for k in keys_to_clear:
                del st.session_state[k]
            
            st.rerun()

    st.markdown("---")

    # --- TABS PER LA RICERCA E SELEZIONE ---
    tab1, tab2 = st.tabs(["Rimuovi Testo", "Rimuovi Immagini"])

    with tab1:
        search_query = st.text_input("Inserisci una parte del testo da cercare:")
        
        if st.button("Cerca Testo"):
            results = []
            if search_query:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    blocks = page.get_text("blocks")
                    for i, block in enumerate(blocks):
                        text = block[4].strip()
                        if search_query.lower() in text.lower():
                            rect = fitz.Rect(block[:4])
                            results.append({
                                "id": f"text_p{page_num}_b{i}",
                                "type": "text",
                                "page": page_num,
                                "rect": rect,
                                "text": text
                            })
                st.session_state.search_results = results
                if not results:
                    st.warning("Nessun testo trovato.")
            else:
                st.warning("Inserisci un testo da cercare.")

        if st.session_state.get('search_results'):
            st.write("Seleziona i testi da eliminare:")
            for res in st.session_state.search_results:
                label = f"Pagina {res['page'] + 1}: {res['text'].replace(chr(10), ' ')}"
                st.checkbox(label, key=res["id"])

    with tab2:
        if not st.session_state.get('images_found'):
            st.info("Nessuna immagine trovata nel documento (o estrazione in corso...).")
        else:
            # Pulsanti per selezione/deselezione massiva
            col_btn1, col_btn2, _ = st.columns([1, 1, 2])
            with col_btn1:
                st.button("Seleziona Tutte le Immagini", on_click=select_all_images)
            with col_btn2:
                st.button("Deseleziona Tutte", on_click=deselect_all_images)
            
            st.write("Seleziona manualmente le immagini da eliminare o da conservare:")
            
            cols = st.columns(4)
            for i, img_data in enumerate(st.session_state.images_found):
                with cols[i % 4]:
                    st.write(f"**Pagina {img_data['page'] + 1}**")
                    st.image(img_data["preview"])
                    st.checkbox("Rimuovi", key=img_data["id"])
