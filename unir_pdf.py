import streamlit as st
import io
import zipfile
from datetime import datetime

try:
    from PyPDF2 import PdfMerger, PdfReader, PdfWriter
except ImportError:
    st.error("❌ PyPDF2 no está instalado. Por favor, asegúrate de que está en requirements.txt")
    st.stop()

# Configuración de la página
st.set_page_config(
    page_title="PDF Toolkit - Unir, Dividir y Eliminar Páginas",
    page_icon="📄",
    layout="wide"
)

# Función para procesar un PDF individual (eliminar páginas)
def process_single_pdf(pdf_file, pages_to_remove):
    try:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer = PdfWriter()
        
        total_pages = len(pdf_reader.pages)
        pages_to_keep = [i for i in range(total_pages) if i not in pages_to_remove]
        
        for page_num in pages_to_keep:
            pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # Guardar PDF procesado en memoria
        buffer = io.BytesIO()
        pdf_writer.write(buffer)
        buffer.seek(0)
        
        return buffer, total_pages, len(pages_to_keep)
    except Exception as e:
        raise Exception(f"Error procesando PDF: {str(e)}")

# Función para unir PDFs ya procesados
def merge_processed_pdfs(processed_pdfs):
    try:
        merger = PdfMerger()
        
        for pdf_buffer in processed_pdfs:
            merger.append(pdf_buffer)
        
        # Guardar PDF unido en memoria
        merged_buffer = io.BytesIO()
        merger.write(merged_buffer)
        merger.close()
        merged_buffer.seek(0)
        
        return merged_buffer
    except Exception as e:
        raise Exception(f"Error uniendo PDFs: {str(e)}")

# Función para dividir PDF
def split_pdf(pdf_file, split_option, custom_ranges=None):
    try:
        pdf_reader = PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        pdf_files = []
        
        if split_option == "todas":
            # Crear un PDF por cada página
            for page_num in range(total_pages):
                pdf_writer = PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_num])
                
                buffer = io.BytesIO()
                pdf_writer.write(buffer)
                buffer.seek(0)
                pdf_files.append(buffer)
        
        elif split_option == "rango_personalizado" and custom_ranges:
            # Dividir según rangos personalizados
            for range_str in custom_ranges:
                pdf_writer = PdfWriter()
                
                if '-' in range_str:
                    try:
                        start, end = map(int, range_str.split('-'))
                        start = max(1, start) - 1
                        end = min(total_pages, end)
                        
                        for page_num in range(start, end):
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                    except ValueError:
                        continue
                else:
                    try:
                        page_num = int(range_str) - 1
                        if 0 <= page_num < total_pages:
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                    except ValueError:
                        continue
                
                buffer = io.BytesIO()
                pdf_writer.write(buffer)
                buffer.seek(0)
                pdf_files.append(buffer)
        
        return pdf_files
    except Exception as e:
        raise Exception(f"Error dividiendo PDF: {str(e)}")

# Función para parsear páginas
def parse_pages_input(pages_input, total_pages=None):
    pages_to_remove = set()
    if not pages_input or not pages_input.strip():
        return pages_to_remove
    
    parts = pages_input.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                # Ajustar a índice 0-based y validar
                start_idx = max(0, start - 1)
                end_idx = end  # end es exclusivo en range
                if total_pages:
                    end_idx = min(end_idx, total_pages)
                pages_to_remove.update(range(start_idx, end_idx))
            except ValueError:
                continue
        else:
            try:
                page_num = int(part) - 1
                if total_pages is None or (0 <= page_num < total_pages):
                    pages_to_remove.add(page_num)
            except ValueError:
                continue
    
    return pages_to_remove

# Interfaz principal
def main():
    st.title("📄 PDF Toolkit - Unir, Dividir y Eliminar Páginas")
    st.markdown("Una herramienta completa para manipular archivos PDF")
    
    # Crear pestañas
    tab1, tab2 = st.tabs(["🔗 Unir y Eliminar Páginas", "✂️ Dividir PDF"])
    
    with tab1:
        st.header("Unir PDFs y Eliminar Páginas")
        
        uploaded_files = st.file_uploader(
            "Selecciona los archivos PDF a unir",
            type="pdf",
            accept_multiple_files=True,
            help="Puedes seleccionar múltiples archivos PDF",
            key="merge_uploader"
        )
        
        if uploaded_files:
            st.subheader("📋 Configurar páginas a eliminar por cada PDF")
            
            # Inicializar session state para páginas si no existe
            if 'pages_inputs' not in st.session_state:
                st.session_state.pages_inputs = {}
            
            # Procesar cada archivo
            for i, file in enumerate(uploaded_files):
                try:
                    file.seek(0)
                    pdf_reader = PdfReader(file)
                    total_pages = len(pdf_reader.pages)
                    
                    with st.expander(f"📄 {file.name} ({total_pages} páginas)", expanded=True):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # Usar session state para mantener el valor
                            key = f"pages_{i}_{file.name}"
                            if key not in st.session_state.pages_inputs:
                                st.session_state.pages_inputs[key] = ""
                            
                            pages_input = st.text_input(
                                f"Páginas a eliminar de {file.name}",
                                value=st.session_state.pages_inputs[key],
                                key=key,
                                placeholder=f"Ej: 1,3,5-7 (de {total_pages} páginas totales)",
                                help=f"Eliminar páginas antes de unir. PDF tiene {total_pages} páginas."
                            )
                            st.session_state.pages_inputs[key] = pages_input
                        
                        with col2:
                            st.metric("Total páginas", total_pages)
                            
                            if pages_input:
                                pages_to_remove = parse_pages_input(pages_input, total_pages)
                                st.metric("Páginas a eliminar", len(pages_to_remove))
                                st.metric("Páginas que quedarán", total_pages - len(pages_to_remove))
                                
                                if pages_to_remove:
                                    st.info(f"Eliminar: {', '.join(map(str, sorted([p+1 for p in pages_to_remove])))}")
                            else:
                                st.metric("Páginas a eliminar", 0)
                                st.metric("Páginas que quedarán", total_pages)
                
                except Exception as e:
                    st.error(f"Error leyendo {file.name}: {str(e)}")
            
            # Botón de procesamiento
            if st.button("🔄 Procesar y Unir PDFs", type="primary", key="merge_button"):
                try:
                    with st.spinner("Procesando PDFs individualmente y uniendo..."):
                        processed_pdfs = []
                        total_stats = {
                            'original_pages': 0,
                            'removed_pages': 0,
                            'final_pages': 0,
                            'processed_files': 0
                        }
                        
                        # Procesar cada PDF individualmente
                        for i, file in enumerate(uploaded_files):
                            file.seek(0)
                            
                            # Obtener páginas a eliminar para este archivo
                            key = f"pages_{i}_{file.name}"
                            pages_input = st.session_state.pages_inputs.get(key, "")
                            pages_to_remove = parse_pages_input(pages_input)
                            
                            # Procesar el PDF individual
                            processed_pdf, original_pages, final_pages = process_single_pdf(file, pages_to_remove)
                            
                            processed_pdfs.append(processed_pdf)
                            total_stats['original_pages'] += original_pages
                            total_stats['removed_pages'] += len(pages_to_remove)
                            total_stats['final_pages'] += final_pages
                            total_stats['processed_files'] += 1
                        
                        # Unir todos los PDFs procesados
                        final_pdf = merge_processed_pdfs(processed_pdfs)
                        
                        # Mostrar resultado
                        st.success("✅ PDFs procesados y unidos correctamente!")
                        
                        # Estadísticas detalladas
                        st.subheader("📊 Resumen del Procesamiento")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Archivos procesados", total_stats['processed_files'])
                        with col2:
                            st.metric("Páginas originales", total_stats['original_pages'])
                        with col3:
                            st.metric("Páginas eliminadas", total_stats['removed_pages'])
                        with col4:
                            st.metric("Páginas finales", total_stats['final_pages'])
                        
                        # Botón de descarga
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.download_button(
                            label="📥 Descargar PDF Procesado",
                            data=final_pdf.getvalue(),
                            file_name=f"pdf_unido_{timestamp}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar los PDFs: {str(e)}")
    
    with tab2:
        st.header("✂️ Dividir PDF")
        
        uploaded_file_split = st.file_uploader(
            "Selecciona el PDF a dividir",
            type="pdf",
            key="split_uploader"
        )
        
        if uploaded_file_split:
            try:
                uploaded_file_split.seek(0)
                pdf_reader = PdfReader(uploaded_file_split)
                total_pages = len(pdf_reader.pages)
                
                st.info(f"📄 **{uploaded_file_split.name}** - {total_pages} páginas")
                
                split_option = st.radio(
                    "Cómo quieres dividir el PDF:",
                    ["todas", "rango_personalizado"],
                    format_func=lambda x: "Dividir en páginas individuales" if x == "todas" else "Dividir por rangos personalizados",
                    key="split_option"
                )
                
                if split_option == "rango_personalizado":
                    st.subheader("Configurar rangos de división")
                    ranges_input = st.text_area(
                        "Especifica los rangos de páginas (uno por línea):",
                        placeholder="Ejemplo:\n1-3\n4-5\n6\n7-10",
                        help="Cada línea será un PDF separado. Usa formato: 1-3, 4, 5-7, etc.",
                        key="ranges_input"
                    )
                    ranges_list = [r.strip() for r in ranges_input.split('\n') if r.strip()] if ranges_input else []
                else:
                    ranges_list = None
                
                if st.button("✂️ Dividir PDF", type="primary", key="split_button"):
                    with st.spinner("Dividiendo PDF..."):
                        pdf_files = split_pdf(uploaded_file_split, split_option, ranges_list)
                        
                        if not pdf_files:
                            st.warning("No se generaron archivos. Verifica los rangos especificados.")
                            return
                        
                        st.success(f"✅ PDF dividido en {len(pdf_files)} archivos!")
                        
                        # Para muchas páginas, ofrecer ZIP
                        if len(pdf_files) > 5:
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                                for i, pdf_buffer in enumerate(pdf_files):
                                    if split_option == "todas":
                                        zip_file.writestr(f"pagina_{i+1}.pdf", pdf_buffer.getvalue())
                                    else:
                                        range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                        zip_file.writestr(f"rango_{range_name}.pdf", pdf_buffer.getvalue())
                            zip_buffer.seek(0)
                            
                            st.download_button(
                                label="📦 Descargar todos como ZIP",
                                data=zip_buffer.getvalue(),
                                file_name="pdf_divididos.zip",
                                mime="application/zip"
                            )
                        
                        # Descargar individualmente
                        st.subheader("Descargar archivos individualmente:")
                        cols = st.columns(2)
                        for i, pdf_buffer in enumerate(pdf_files):
                            with cols[i % 2]:
                                if split_option == "todas":
                                    st.download_button(
                                        label=f"📄 Página {i+1}",
                                        data=pdf_buffer.getvalue(),
                                        file_name=f"pagina_{i+1}.pdf",
                                        mime="application/pdf",
                                        key=f"page_{i}"
                                    )
                                else:
                                    range_name = ranges_list[i] if i < len(ranges_list) else f"rango_{i+1}"
                                    st.download_button(
                                        label=f"📄 Rango: {range_name}",
                                        data=pdf_buffer.getvalue(),
                                        file_name=f"rango_{range_name}.pdf",
                                        mime="application/pdf",
                                        key=f"range_{i}"
                                    )
            
            except Exception as e:
                st.error(f"Error procesando archivo: {str(e)}")

    # Instrucciones
    with st.expander("📖 Instrucciones de uso"):
        st.markdown("""
        ### 🔗 Unir y Eliminar Páginas:
        1. **Cargar PDFs**: Selecciona múltiples archivos PDF
        2. **Configurar cada PDF**: Para cada archivo, especifica qué páginas eliminar ANTES de unir
        3. **Formato de páginas**: Usa:
           - Páginas individuales: `1,3,5`
           - Rangos: `2-4`
           - Combinación: `1,3,5-7`
        4. **Procesar**: Los PDFs se procesan individualmente y luego se unen

        ### ✂️ Dividir PDF:
        1. **Cargar PDF**: Selecciona un archivo PDF
        2. **Elegir modo**:
           - **Páginas individuales**: Crea un PDF por cada página
           - **Rangos personalizados**: Divide en grupos específicos de páginas
        3. **Especificar rangos** (si aplica): Un rango por línea, ej: `1-3`, `4`, `5-7`
        4. **Dividir**: Descarga los archivos resultantes

        **Nota**: Todos los procesamientos se hacen en memoria, tus archivos están seguros.
        """)
    
    # Pie de página
    st.markdown("---")
    st.markdown("Creado con Streamlit y PyPDF2 • Tus archivos se procesan localmente")

if __name__ == "__main__":
    main()