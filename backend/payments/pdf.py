from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .choices import ReceiptStatus


TEAL = colors.HexColor("#174F52")
TEAL_SOFT = colors.HexColor("#E7F0EC")
INK = colors.HexColor("#243B3B")
MUTED = colors.HexColor("#687B78")
LINE = colors.HexColor("#D7E1DB")
RED = colors.HexColor("#A94739")


def safe(value):
    return escape(str(value or ""))


def money(value):
    return f"L {value:,.2f}"


def build_receipt_pdf(receipt):
    payment = receipt.payment
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A5, leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=13 * mm, bottomMargin=14 * mm,
        title=f"Recibo {receipt.receipt_number}", author=receipt.organization_name_snapshot,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="RBrand", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=TEAL))
    styles.add(ParagraphStyle(name="RTitle", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=MUTED))
    styles.add(ParagraphStyle(name="RBody", fontName="Helvetica", fontSize=7.5, leading=10, textColor=INK))
    styles.add(ParagraphStyle(name="RSmall", fontName="Helvetica", fontSize=6.5, leading=8.5, textColor=MUTED))
    styles.add(ParagraphStyle(name="RSection", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=TEAL, spaceBefore=7, spaceAfter=5))
    styles.add(ParagraphStyle(name="RAmount", fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=TEAL, alignment=TA_RIGHT))
    story = []
    logo = ""
    if receipt.organization.logo:
        try:
            logo = Image(receipt.organization.logo.path, width=16 * mm, height=16 * mm, kind="proportional")
        except (FileNotFoundError, OSError, ValueError):
            logo = ""
    header = Table([[logo, [
        Paragraph(safe(receipt.organization_name_snapshot), styles["RBrand"]),
        Paragraph("RECIBO DE PAGO", styles["RTitle"]),
    ], Paragraph(f"<b>{safe(receipt.receipt_number)}</b><br/>{receipt.issued_at.strftime('%d/%m/%Y %H:%M')}", styles["RBody"])]],
        colWidths=[18 * mm, 73 * mm, 35 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 1, TEAL), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([header, Spacer(1, 3 * mm)])
    if receipt.status == ReceiptStatus.VOIDED:
        void_table = Table([[Paragraph("ANULADO", ParagraphStyle(
            name="RVoid", parent=styles["RTitle"], textColor=RED, alignment=TA_CENTER, fontSize=12,
        ))]], colWidths=[126 * mm])
        void_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, RED), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9E8E4")), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.extend([void_table, Spacer(1, 2 * mm)])
    story.append(Paragraph("RECIBIMOS DE", styles["RSection"]))
    customer = Table([
        ["Cliente", Paragraph(safe(receipt.customer_name_snapshot), styles["RBody"]), "Código", receipt.customer_code_snapshot],
        ["Identidad", receipt.customer_identity_snapshot or "No registrada", "Contrato", receipt.contract_number_snapshot],
    ], colWidths=[18 * mm, 49 * mm, 18 * mm, 41 * mm])
    customer.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), .35, LINE), ("BACKGROUND", (0, 0), (0, -1), TEAL_SOFT),
        ("BACKGROUND", (2, 0), (2, -1), TEAL_SOFT), ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([customer, Spacer(1, 3 * mm)])
    amount_box = Table([[
        [Paragraph("CONCEPTO", styles["RSmall"]), Paragraph(safe(receipt.concept_snapshot), styles["RBody"])],
        Paragraph(money(receipt.amount_snapshot), styles["RAmount"]),
    ]], colWidths=[70 * mm, 56 * mm])
    amount_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .7, LINE), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8F5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(amount_box)
    if len(receipt.applications_snapshot) > 14:
        story.extend([
            Paragraph(
                f"El pago contiene {len(receipt.applications_snapshot)} aplicaciones. El detalle continúa en la página siguiente.",
                styles["RSmall"],
            ),
            PageBreak(),
        ])
    story.append(Paragraph("APLICACIÓN DEL PAGO", styles["RSection"]))
    rows = [["Destino", "Vencimiento", "Importe"]]
    for item in receipt.applications_snapshot:
        if item.get("kind") == "installment":
            label = f"Cuota #{item['installment_number']}"
            due = item.get("due_date", "")
        else:
            label = item.get("label", "Saldo contractual")
            due = "-"
        rows.append([label, due, money(Decimal(item["amount"]))])
    application_table = Table(rows, colWidths=[53 * mm, 34 * mm, 39 * mm], repeatRows=1)
    application_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.8), ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), .3, LINE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TEAL_SOFT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(application_table)
    story.append(Paragraph("RESUMEN", styles["RSection"]))
    summary = Table([
        ["Saldo anterior", money(receipt.balance_before)],
        ["Monto recibido", money(receipt.amount_snapshot)],
        ["Saldo posterior", money(receipt.balance_after)],
        ["Método", receipt.method_snapshot],
        ["Referencia", receipt.reference_snapshot or "No aplica"],
    ], colWidths=[55 * mm, 71 * mm])
    summary.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), .3, LINE), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 0), (1, 2), "RIGHT"), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([summary, Spacer(1, 7 * mm)])
    signature = Table([
        ["", ""], [Paragraph("Recibido por", styles["RSmall"]), Paragraph("Firma / sello", styles["RSmall"])],
        [Paragraph(safe(receipt.received_by_snapshot), styles["RBody"]), ""],
    ], colWidths=[61 * mm, 61 * mm])
    signature.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), .5, MUTED), ("LINEABOVE", (1, 1), (1, 1), .5, MUTED),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 1), (-1, -1), 3),
    ]))
    story.append(signature)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Este recibo acredita dinero recibido. Conserve el número para cualquier consulta o anulación controlada.",
        styles["RSmall"],
    ))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(12 * mm, 10 * mm, 136 * mm, 10 * mm)
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(MUTED)
        contact = " · ".join(filter(None, (receipt.organization_phone_snapshot, receipt.organization_address_snapshot)))
        canvas.drawString(12 * mm, 6.5 * mm, contact[:90])
        canvas.drawRightString(136 * mm, 6.5 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
