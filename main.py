import streamlit as st
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET
import pandas as pd
import io
import base64

# Configuración inicial
st.set_page_config(page_title="Lector XML", layout="wide")


st.title("Lector de XML Contabilidad")

uploaded_files = st.file_uploader("Sube uno o más archivos XML", type="xml", accept_multiple_files=True)

# Espacios de nombre y tipos DTE
SII_NS = {'sii': 'http://www.sii.cl/SiiDte'}

DTE_TIPOS = {
    "33": "Factura electrónica",
    "34": "Factura exenta electrónica",
    "39": "Boleta electrónica",
    "41": "Boleta exenta electrónica",
    "52": "Guía de despacho electrónica",
    "56": "Nota de débito electrónica",
    "61": "Nota de crédito electrónica"
}

# Detectar tipo de XML
def detectar_tipo_xml(root):
    tag = root.tag.lower()
    if 'enviodte' in tag:
        return 'EnvioDTE'
    elif 'respuestadte' in tag:
        return 'RespuestaDTE'
    elif 'dte' in tag:
        return 'DTE directo'
    return 'Desconocido'

# Procesar EnvioDTE
def procesar_enviodte(root):
    datos = []
    try:
        dte = root.find('.//sii:DTE', SII_NS)
        doc = dte.find('.//sii:Documento', SII_NS)
        encabezado = doc.find('.//sii:Encabezado', SII_NS)
        detalles = doc.findall('.//sii:Detalle', SII_NS)

        tipo_dte = encabezado.findtext('sii:IdDoc/sii:TipoDTE', '', SII_NS)
        descripcion_dte = DTE_TIPOS.get(tipo_dte, "Desconocido")

        # Buscar VL o BL en Referencias
        referencia = doc.find('.//sii:Referencia', SII_NS)
        referencia_bl_vl = ""
        if referencia is not None:
            tipo_doc_ref = referencia.findtext('sii:TpoDocRef', '', SII_NS)
            if tipo_doc_ref in ['VL', 'BL']:
                folio_ref = referencia.findtext('sii:FolioRef', '', SII_NS)
                referencia_bl_vl = f"{tipo_doc_ref}: {folio_ref}"

        base_info = {
            "Tipo XML": "Factura (EnvioDTE)",
            "Tipo DTE": tipo_dte,
            "Descripción DTE": descripcion_dte,
            "Folio": encabezado.findtext('sii:IdDoc/sii:Folio', '', SII_NS),
            "Fecha Emisión": encabezado.findtext('sii:IdDoc/sii:FchEmis', '', SII_NS),
            "Fecha Vencimiento": encabezado.findtext('sii:IdDoc/sii:FchVenc', '', SII_NS),
            "RUT Emisor": encabezado.findtext('sii:Emisor/sii:RUTEmisor', '', SII_NS),
            "Razón Social Emisor": encabezado.findtext('sii:Emisor/sii:RznSoc', '', SII_NS),
            "Dirección Emisor": encabezado.findtext('sii:Emisor/sii:DirOrigen', '', SII_NS),
            "RUT Receptor": encabezado.findtext('sii:Receptor/sii:RUTRecep', '', SII_NS),
            "Razón Social Receptor": encabezado.findtext('sii:Receptor/sii:RznSocRecep', '', SII_NS),
            "Dirección Receptor": encabezado.findtext('sii:Receptor/sii:DirRecep', '', SII_NS),
            "Monto Exento": encabezado.findtext('sii:Totales/sii:MntExe', '', SII_NS),
            "Monto Total": encabezado.findtext('sii:Totales/sii:MntTotal', '', SII_NS),
        }

        for detalle in detalles:
            dsc_item = detalle.findtext('sii:DscItem', '', SII_NS)
            bl_detectado = ""
            if "BL:" in dsc_item:
                try:
                    bl_detectado = dsc_item.split("BL:")[1].strip()
                except:
                    bl_detectado = ""

            item = {
                "Descripción Item": detalle.findtext('sii:NmbItem', '', SII_NS),
                "Cantidad": detalle.findtext('sii:QtyItem', '', SII_NS),
                "Precio Unitario": detalle.findtext('sii:PrcItem', '', SII_NS),
                "Monto Item": detalle.findtext('sii:MontoItem', '', SII_NS),
                "BL Detectado": bl_detectado
            }

            datos.append({**base_info, **item})

    except Exception as e:
        datos.append({"Tipo XML": "Factura (EnvioDTE)", "Error": str(e)})

    return datos

# Procesar RespuestaDTE
def procesar_respuestadte(root):
    datos = []
    try:
        resultados = root.findall('.//sii:ResultadoDTE', SII_NS)
        for resultado in resultados:
            datos.append({
                "Tipo XML": "RespuestaDTE",
                "RUT Receptor": resultado.findtext('sii:RutRecep', '', SII_NS),
                "RUT Emisor": resultado.findtext('sii:RutEmisor', '', SII_NS),
                "Tipo DTE": resultado.findtext('sii:TipoDTE', '', SII_NS),
                "Folio": resultado.findtext('sii:Folio', '', SII_NS),
                "Estado Recepción": resultado.findtext('sii:EstadoRecepDTE', '', SII_NS),
                "Glosa Estado": resultado.findtext('sii:GlosaRecepDTE', '', SII_NS)
            })
    except Exception as e:
        datos.append({"Tipo XML": "RespuestaDTE", "Error": str(e)})
    return datos

# Procesar archivos cargados
datos_finales = []
if uploaded_files:
    for archivo in uploaded_files:
        try:
            content = archivo.read()
            root = ET.fromstring(content)
            tipo = detectar_tipo_xml(root)

            if tipo == 'EnvioDTE':
                datos_finales.extend(procesar_enviodte(root))
            elif tipo == 'RespuestaDTE':
                datos_finales.extend(procesar_respuestadte(root))
            else:
                datos_finales.append({"Tipo XML": tipo, "Error": "Formato no reconocido", "Archivo": archivo.name})

        except Exception as e:
            datos_finales.append({"Tipo XML": "Error", "Error": str(e), "Archivo": archivo.name})

    # Mostrar tabla
    df = pd.DataFrame(datos_finales)
    st.success(f" {len(df)} líneas procesadas.")
    st.dataframe(df, use_container_width=True)

    # Descargar Excel
    excel = io.BytesIO()
    df.to_excel(excel, index=False, engine='openpyxl')
    st.download_button(" Descargar Excel", data=excel.getvalue(),
                       file_name="facturas_sii.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Footer
footer = """
<style>
.footer {
    position: fixed;
    bottom: 0;
    width: 100%;
    background-color: #f0f2f6;
    text-align: center;
    font-size: 13px;
    color: #6c757d;
    padding: 10px;
}
</style>
<div class="footer">
    © 2025 Sistema desarrollado por <strong>Soporte Ingefix</strong>.
</div>
"""
components.html(footer, height=50)
