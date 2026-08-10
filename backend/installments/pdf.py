from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


TEAL = colors.HexColor("#174F50")
TEAL_SOFT = colors.HexColor("#E8F0ED")
INK = colors.HexColor("#243B3B")
MUTED = colors.HexColor("#667B78")
LINE = colors.HexColor("#D9E2DC")
SAND = colors.HexColor("#F5F2E9")


def safe(value):
    return escape(str(value or ""))


def money(value):
    return f"L {value:,.2f}"


def build_payment_plan_pdf(schedule):
    contract = schedule.contract
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Plan de pagos {contract.contract_number}", author=contract.organization.name,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="PlanBrand", fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=TEAL,
    ))
    styles.add(ParagraphStyle(
        name="PlanSubtitle", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=MUTED,
    ))
    styles.add(ParagraphStyle(
        name="PlanSection", fontName="Helvetica-Bold", fontSize=9, leading=12,
        textColor=TEAL, spaceBefore=10, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="PlanBody", fontName="Helvetica", fontSize=8.2, leading=11, textColor=INK,
    ))
    styles.add(ParagraphStyle(
        name="PlanSmall", fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED,
    ))
    styles.add(ParagraphStyle(
        name="PlanMoney", fontName="Helvetica-Bold", fontSize=11, leading=13,
        textColor=TEAL, alignment=TA_RIGHT,
    ))

    logo = ""
    if contract.organization.logo:
        try:
            logo = Image(contract.organization.logo.path, width=20 * mm, height=20 * mm, kind="proportional")
        except (FileNotFoundError, OSError, ValueError):
            logo = ""
    story = []
    header = Table([[
        logo,
        [Paragraph(safe(contract.organization.name), styles["PlanBrand"]),
         Paragraph("PLAN DE PAGOS", styles["PlanSubtitle"])],
        Paragraph(f"<b>{safe(contract.contract_number)}</b><br/>Calendario v{schedule.version}", styles["PlanBody"]),
    ]], colWidths=[23 * mm, 103 * mm, 46 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("LINEBELOW", (0, 0), (-1, -1), 1.2, TEAL),
    ]))
    story.extend([header, Spacer(1, 5 * mm)])
    story.append(Paragraph("DATOS CONTRACTUALES", styles["PlanSection"]))
    details = Table([
        ["Cliente", contract.customer_name_snapshot, "Identidad", contract.customer_identity_snapshot or "No registrada"],
        ["Plan", contract.plan_name_snapshot, "Sucursal", contract.branch.name],
        ["Total contrato", money(contract.total_price), "Prima acordada", money(contract.initial_payment_agreed)],
        ["Monto financiado", money(schedule.total_financed), "Frecuencia", schedule.get_frequency_display()],
    ], colWidths=[28 * mm, 58 * mm, 28 * mm, 58 * mm])
    details.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, LINE), ("INNERGRID", (0, 0), (-1, -1), .35, LINE),
        ("BACKGROUND", (0, 0), (0, -1), TEAL_SOFT), ("BACKGROUND", (2, 0), (2, -1), TEAL_SOFT),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(details)
    story.append(Paragraph("CRONOGRAMA DE OBLIGACIONES", styles["PlanSection"]))
    rows = [["Cuota", "Vencimiento", "Importe", "Naturaleza"]]
    for installment in schedule.installments.order_by("installment_number"):
        rows.append([
            str(installment.installment_number), installment.due_date.strftime("%d/%m/%Y"),
            money(installment.original_amount), "Obligación programada",
        ])
    table = Table(rows, colWidths=[24 * mm, 42 * mm, 45 * mm, 61 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TEAL_SOFT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    summary = Table([[
        Paragraph(f"<b>{schedule.total_installments}</b> cuotas", styles["PlanBody"]),
        Paragraph(f"Desde <b>{schedule.first_due_date.strftime('%d/%m/%Y')}</b>", styles["PlanBody"]),
        Paragraph(f"Hasta <b>{schedule.last_due_date.strftime('%d/%m/%Y')}</b>", styles["PlanBody"]),
        Paragraph(money(schedule.total_financed), styles["PlanMoney"]),
    ]], colWidths=[38 * mm, 45 * mm, 45 * mm, 44 * mm])
    summary.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .7, LINE), ("BACKGROUND", (0, 0), (-1, -1), SAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([Spacer(1, 4 * mm), summary, Spacer(1, 4 * mm)])
    story.append(Paragraph(
        "Este documento representa obligaciones programadas. No acredita pagos, abonos ni dinero recibido.",
        styles["PlanSmall"],
    ))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(16 * mm, 12 * mm, 194 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 8 * mm, f"Plan de pagos {contract.contract_number} · v{schedule.version}")
        canvas.drawRightString(194 * mm, 8 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
