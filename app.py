import streamlit as st
import fitz
import io
from PIL import Image

st.set_page_config(page_title="Rimuovi Immagini e Testi dal PDF", layout="wide")
st.title("Rimuovi Immagini e Testi dal PDF")
st.write("Carica il PDF. Seleziona le immagini o i testi da eliminare e procedi con la rimozione.")

uploaded_file = st.file_uploader("Carica il file PDF", type="pdf")

if uploaded_file is not None:
    if 'pdf_bytes' not in st.session_state or st.session_state.get('file_name') != uploaded_file.name:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.file_name = uploaded_file.name
        st.session_state.search_results = []
        st.session_state.images_found = []
    
    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
    
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

    tab1, tab2 = st.tabs(["Rimuovi Testo", "Rimuovi Immagini"])

    with tab1:
        search_query = st.text_input("Inserisci una parte del testo da cercare:")
        
        if st.button("Cerca Testo", type="primary"):
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

        if st.session_state.search_results:
            st.write("Seleziona i testi da eliminare:")
            selected_text_blocks = []
            for res in st.session_state.search_results:
                label = f"Pagina {res['page'] + 1}: {res['text'].replace(chr(10), ' ')}"
                if st.checkbox(label, key=res["id"]):
                    selected_text_blocks.append(res)
            st.session_state.selected_texts = selected_text_blocks

    with tab2:
        if st.button("Analizza Immagini nel PDF"):
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
                            # ID reso univoco per pagina per evitare conflitti con immagini ripetute
                            "id": f"img_p{page_num}_{xref}_{img_index}",
                            "type": "image",
                            "xref": xref,
                            "page": page_num,
                            "preview": image
                        })
                    except Exception:
                        continue 
                        
            # Rimosso l'accorpamento tramite unique_images: ora le tiene tutte
            st.session_state.images_found = images_found
            
            if not st.session_state.images_found:
                st.warning("Nessuna immagine trovata nel documento.")

        if st.session_state.images_found:
            st.write("Seleziona le immagini da eliminare:")
            selected_images = []
            
            cols = st.columns(4)
            for i, img_data in enumerate(st.session_state.images_found):
                with cols[i % 4]:
                    # Aggiunta l'indicazione della pagina sopra l'immagine
                    st.write(f"**Pagina {img_data['page'] + 1}**")
                    st.image(img_data["preview"])
                    if st.checkbox("Rimuovi", key=img_data["id"]):
                        selected_images.append(img_data)
            st.session_state.selected_images = selected_images

    st.markdown("---")
    
    texts_to_delete = st.session_state.get('selected_texts', [])
    images_to_delete = st.session_state.get('selected_images', [])
    total_selections = len(texts_to_delete) + len(images_to_delete)

    if st.button(f"Rimuovi Selezionati ({total_selections})", disabled=total_selections==0, type="primary"):
        with st.spinner("Modifica del PDF in corso..."):
            
            pages_to_redact = set()
            for res in texts_to_delete:
                page = doc[res["page"]]
                page.add_redact_annot(res["rect"])
                pages_to_redact.add(res["page"])
                
            for page_num in pages_to_redact:
                page = doc[page_num]
                page.apply_redactions(images=0)
                
            for res in images_to_delete:
                xref = res["xref"]
                # Svuota l'oggetto immagine nel PDF
                doc.xref_set_key(xref, "Subtype", "/Form")
                doc.xref_set_key(xref, "BBox", "[0 0 0 0]")
                doc.xref_set_key(xref, "Width", "null")
                doc.xref_set_key(xref, "Height", "null")
                doc.xref_set_key(xref, "ColorSpace", "null")
                doc.xref_set_key(xref, "Filter", "null")
                doc.update_stream(xref, b"")
            
            out_pdf = io.BytesIO()
            doc.save(out_pdf, garbage=4, deflate=True)
            
            st.session_state.pdf_bytes = out_pdf.getvalue()
            st.session_state.search_results = []
            st.session_state.images_found = []
            st.session_state.selected_texts = []
            st.session_state.selected_images = []
            
            st.rerun()