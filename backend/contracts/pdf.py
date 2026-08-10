from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


TEAL = colors.HexColor("#174F50")
TEAL_SOFT = colors.HexColor("#E8F0ED")
INK = colors.HexColor("#243B3B")
MUTED = colors.HexColor("#667B78")
LINE = colors.HexColor("#D9E2DC")
SAND = colors.HexColor("#F5F2E9")


def money(value):
    return f"L {value:,.2f}"


def safe(value):
    return escape(str(value or ""))


def build_contract_pdf(contract):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm, title=f"Contrato {contract.contract_number}",
        author=contract.organization.name,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Brand", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17,
        leading=20, textColor=TEAL, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="ContractTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11,
        leading=14, textColor=MUTED, spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="PageTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15,
        leading=19, textColor=TEAL, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=9,
        leading=12, textColor=TEAL, spaceBefore=10, spaceAfter=7, uppercase=True,
    ))
    styles.add(ParagraphStyle(
        name="BodySmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.2,
        leading=12, textColor=INK,
    ))
    styles.add(ParagraphStyle(
        name="Label", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=6.8,
        leading=9, textColor=MUTED, uppercase=True,
    ))
    styles.add(ParagraphStyle(
        name="Value", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.7,
        leading=11, textColor=INK,
    ))
    styles.add(ParagraphStyle(
        name="Money", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=12,
        leading=15, textColor=TEAL, alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="Footer", parent=styles["BodyText"], fontName="Helvetica", fontSize=7,
        leading=9, textColor=MUTED, alignment=TA_CENTER,
    ))

    story = []
    logo = None
    if contract.organization.logo:
        try:
            logo = Image(contract.organization.logo.path, width=22 * mm, height=22 * mm, kind="proportional")
        except (FileNotFoundError, OSError, ValueError):
            logo = None
    brand = [
        Paragraph(safe(contract.organization.name), styles["Brand"]),
        Paragraph("CONTRATO DE PLAN FUNERARIO", styles["ContractTitle"]),
    ]
    brand_table = Table(
        [[logo or "", brand, Paragraph(f"<b>{safe(contract.contract_number)}</b><br/><font size='8'>Fecha: {contract.sale_date.strftime('%d/%m/%Y')}</font>", styles["Value"])]],
        colWidths=[25 * mm, 95 * mm, 42 * mm],
    )
    brand_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("LINEBELOW", (0, 0), (-1, -1), 1.2, TEAL),
    ]))
    story.extend([brand_table, Spacer(1, 5 * mm)])

    def info_cell(label, value):
        return [Paragraph(label, styles["Label"]), Paragraph(safe(value) or "No registrado", styles["Value"])]

    story.append(Paragraph("PARTES Y BENEFICIARIO", styles["Section"]))
    party_table = Table([
        [info_cell("Cliente", contract.customer_name_snapshot), info_cell("Identidad", contract.customer_identity_snapshot)],
        [info_cell("Teléfono", contract.customer_phone_snapshot), info_cell("Dirección contractual", contract.customer_address_snapshot)],
        [info_cell("Beneficiario", contract.beneficiary_name_snapshot), info_cell("Identidad / relación", f"{contract.beneficiary_identity_snapshot or 'No registrada'} · {contract.beneficiary_relationship_snapshot}")],
        [info_cell("Vendedor", contract.seller.get_full_name().strip() or contract.seller.username), info_cell("Sucursal", contract.branch.name)],
    ], colWidths=[81 * mm, 81 * mm])
    party_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .6, LINE), ("INNERGRID", (0, 0), (-1, -1), .4, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(party_table)

    story.append(Paragraph("PLAN Y PRESTACIONES CONTRATADAS", styles["Section"]))
    story.append(Paragraph(f"<b>{safe(contract.plan_name_snapshot)}</b><br/>{safe(contract.plan_description_snapshot)}", styles["BodySmall"]))
    story.append(Spacer(1, 3 * mm))
    item_rows = [["Cant.", "Prestación", "Categoría / unidad", "Notas"]]
    for item in contract.plan_items.all():
        item_rows.append([
            f"{item.quantity:g}",
            Paragraph(f"<b>{safe(item.service_name_snapshot)}</b><br/><font size='7'>{safe(item.service_code_snapshot)}</font>", styles["BodySmall"]),
            Paragraph(f"{safe(item.category_snapshot)}<br/>{safe(item.unit_snapshot)}", styles["BodySmall"]),
            Paragraph(safe(item.notes_snapshot) or "-", styles["BodySmall"]),
        ])
    item_table = Table(item_rows, colWidths=[14 * mm, 70 * mm, 38 * mm, 40 * mm], repeatRows=1)
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ALIGN", (0, 0), (0, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), .4, LINE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TEAL_SOFT]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(item_table)

    story.append(Paragraph("CONDICIONES COMERCIALES", styles["Section"]))
    financial_rows = [
        [Paragraph("Precio del plan", styles["Label"]), Paragraph(money(contract.subtotal), styles["Money"])],
        [Paragraph("Descuento autorizado", styles["Label"]), Paragraph(money(contract.discount), styles["Money"])],
        [Paragraph("VALOR TOTAL DEL CONTRATO", styles["Value"]), Paragraph(money(contract.total_price), styles["Money"])],
        [Paragraph("Prima acordada (no implica pago recibido)", styles["Label"]), Paragraph(money(contract.initial_payment_agreed), styles["Money"])],
        [Paragraph("Monto sujeto a financiamiento", styles["Label"]), Paragraph(money(contract.financed_amount), styles["Money"])],
    ]
    financial_table = Table(financial_rows, colWidths=[100 * mm, 62 * mm])
    financial_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .6, LINE), ("INNERGRID", (0, 0), (-1, -1), .4, LINE),
        ("BACKGROUND", (0, 2), (-1, 2), SAND), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(financial_table)
    story.extend([
        PageBreak(),
        Paragraph("CONDICIONES Y ACEPTACIÓN", styles["PageTitle"]),
        Paragraph(f"Anexo inseparable del contrato {safe(contract.contract_number)}", styles["ContractTitle"]),
        Spacer(1, 5 * mm),
    ])
    continuation = Table([[
        info_cell("Contrato", contract.contract_number),
        info_cell("Plan", contract.plan_name_snapshot),
        info_cell("Valor total", money(contract.total_price)),
    ]], colWidths=[48 * mm, 68 * mm, 46 * mm])
    continuation.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .6, LINE), ("INNERGRID", (0, 0), (-1, -1), .4, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), TEAL_SOFT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([continuation, Spacer(1, 5 * mm)])
    if contract.allow_financing:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Financiamiento: {safe(contract.get_payment_frequency_display())}. Cuota esperada: <b>{money(contract.installment_amount)}</b>. "
            f"Primer vencimiento: <b>{contract.first_due_date.strftime('%d/%m/%Y')}</b>. El calendario de pagos se generará en el módulo correspondiente.",
            styles["BodySmall"],
        ))
    else:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Modalidad: <b>Venta al contado</b>. Este contrato no acredita que el dinero haya sido recibido.", styles["BodySmall"]))

    story.append(Paragraph("CONDICIONES GENERALES", styles["Section"]))
    conditions = (
        "Las partes declaran que la información anterior refleja las condiciones comerciales aceptadas al confirmar la venta. "
        "La prima acordada y las cuotas esperadas no constituyen comprobantes de pago. Los pagos reales deberán documentarse "
        "mediante los recibos y procesos financieros habilitados por la empresa. Las prestaciones se regirán por este snapshot "
        "contractual aunque el catálogo comercial cambie posteriormente."
    )
    story.append(Paragraph(conditions, styles["BodySmall"]))
    if contract.notes:
        story.extend([Paragraph("OBSERVACIONES", styles["Section"]), Paragraph(safe(contract.notes), styles["BodySmall"])])

    signatures = Table([
        ["", ""],
        [Paragraph("Firma del cliente", styles["Footer"]), Paragraph("Firma del representante", styles["Footer"])],
        [Paragraph(safe(contract.customer_name_snapshot), styles["Footer"]), Paragraph(safe(contract.organization.name), styles["Footer"])],
    ], colWidths=[76 * mm, 76 * mm], rowHeights=[18 * mm, 6 * mm, 5 * mm], hAlign="CENTER")
    signatures.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), .7, INK), ("LINEABOVE", (1, 1), (1, 1), .7, INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([Spacer(1, 9 * mm), KeepTogether(signatures)])

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(17 * mm, 12 * mm, 193 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(17 * mm, 8 * mm, f"Contrato {contract.contract_number} · Documento histórico")
        canvas.drawRightString(193 * mm, 8 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
