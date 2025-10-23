import streamlit as st
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io
import os

st.set_page_config(page_title="Unir y Eliminar Páginas PDF", page_icon="📄")

st.title("📄 Unir PDFs y Eliminar Páginas")
st.markdown("""
Esta aplicación te permite:
1. **Unir múltiples archivos PDF** en uno solo
2. **Eliminar páginas específicas** de los PDFs
""")

# Función para procesar PDFs
def process_pdfs(pdf_files, pages_to_remove):
    merger = PdfMerger()
    pdf_writer = PdfWriter()
    
    # Unir todos los PDFs
    for pdf_file in pdf_files:
        merger.append(pdf_file)
    
    # Guardar PDF unido en memoria
    merged_buffer = io.BytesIO()
    merger.write(merged_buffer)
    merger.close()
    
    # Leer PDF unido
    merged_buffer.seek(0)
    pdf_reader = PdfReader(merged_buffer)
    
    # Eliminar páginas especificadas
    total_pages = len(pdf_reader.pages)
    pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
    
    for page_num in pages_to_keep:
        pdf_writer.add_page(pdf_reader.pages[page_num])
    
    # Guardar PDF final
    final_buffer = io.BytesIO()
    pdf_writer.write(final_buffer)
    final_buffer.seek(0)
    
    return final_buffer

# Interfaz de usuario
uploaded_files = st.file_uploader(
    "Selecciona los archivos PDF a unir",
    type="pdf",
    accept_multiple_files=True,
    help="Puedes seleccionar múltiples archivos PDF"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} archivo(s) PDF cargado(s)")
    
    # Mostrar nombres de archivos cargados
    with st.expander("Ver archivos cargados"):
        for file in uploaded_files:
            st.write(f"📄 {file.name}")

    # Configuración de páginas a eliminar
    st.subheader("Configurar páginas a eliminar")
    
    # Calcular total de páginas después de unir
    total_pages = 0
    for pdf_file in uploaded_files:
        pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        total_pages += len(reader.pages)
    
    st.info(f"El PDF unido tendrá {total_pages} páginas en total")
    
    # Entrada para páginas a eliminar
    pages_input = st.text_input(
        "Páginas a eliminar (ej: 1,3,5-7)",
        help="Usa comas para páginas individuales y guiones para rangos"
    )

    # Procesar PDFs
    if st.button("Procesar PDFs", type="primary"):
        if not pages_input:
            st.warning("⚠️ Ingresa las páginas que deseas eliminar")
        else:
            try:
                # Parsear entrada de páginas
                pages_to_remove = set()
                parts = pages_input.split(',')
                
                for part in parts:
                    if '-' in part:
                        start, end = map(int, part.split('-'))
                        pages_to_remove.update(range(start-1, end))
                    else:
                        pages_to_remove.add(int(part)-1)
                
                # Validar páginas
                invalid_pages = [p+1 for p in pages_to_remove if p < 0 or p >= total_pages]
                if invalid_pages:
                    st.error(f"❌ Páginas inválidas: {invalid_pages}. El PDF tiene {total_pages} páginas.")
                else:
                    with st.spinner("Procesando PDFs..."):
                        # Reiniciar posición de archivos
                        for pdf_file in uploaded_files:
                            pdf_file.seek(0)
                        
                        # Procesar PDFs
                        result_pdf = process_pdfs(uploaded_files, pages_to_remove)
                        
                        # Descargar resultado
                        st.success("✅ PDF procesado correctamente!")
                        st.download_button(
                            label="📥 Descargar PDF Procesado",
                            data=result_pdf,
                            file_name="pdf_procesado.pdf",
                            mime="application/pdf"
                        )
                        
            except Exception as e:
                st.error(f"❌ Error al procesar: {str(e)}")

else:
    st.info("👆 Carga uno o más archivos PDF para comenzar")

# Instrucciones
with st.expander("📖 Instrucciones de uso"):
    st.markdown("""
    1. **Cargar PDFs**: Selecciona todos los archivos PDF que quieres unir
    2. **Especificar páginas**: Indica las páginas a eliminar usando:
       - Páginas individuales: `1,3,5`
       - Rangos de páginas: `2-4`
       - Combinación: `1,3,5-7`
    3. **Procesar**: Haz clic en "Procesar PDFs"
    4. **Descargar**: Usa el botón de descarga para obtener el resultado

    **Notas**:
    - Las páginas se numeran desde 1
    - El PDF resultante mantendrá el orden de los archivos cargados
    - Las páginas eliminadas se remueven después de unir todos los PDFs
    """)

# Pie de página
st.markdown("---")
st.markdown("Creado con Streamlit y PyPDF2")