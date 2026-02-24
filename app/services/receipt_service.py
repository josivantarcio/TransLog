"""Serviço de geração de Comprovante de Entrega em PDF.

Gera um PDF profissional com os dados da entrega após status DELIVERED.
Usa reportlab para gerar o PDF em memória (sem I/O em disco).
"""

import io
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.delivery import Delivery, DeliveryStatus


def _fmt_dt(dt: datetime | None) -> str:
    """Formata datetime para exibição no Brasil (UTC-3 simplificado)."""
    if dt is None:
        return "—"
    # Exibe sempre UTC com indicação
    return dt.strftime("%d/%m/%Y %H:%M") + " UTC"


def _fmt_float(val) -> str:
    if val is None:
        return "—"
    return str(val)


class DeliveryReceiptService:
    """Gera comprovante de entrega em PDF usando reportlab."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_delivered_delivery(self, tenant_id: UUID, delivery_id: UUID) -> Delivery:
        result = await self.db.execute(
            select(Delivery).where(
                Delivery.id == delivery_id,
                Delivery.tenant_id == tenant_id,
            )
        )
        delivery = result.scalar_one_or_none()
        if not delivery:
            raise ValueError("Entrega não encontrada.")
        if delivery.status != DeliveryStatus.DELIVERED:
            raise ValueError("Comprovante disponível apenas para entregas concluídas (DELIVERED).")
        return delivery

    def generate_pdf(self, delivery: Delivery) -> bytes:
        """Gera o PDF em memória e retorna os bytes."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
            HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1a237e"),
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=10,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=12,
            spaceAfter=4,
            spaceBefore=10,
            textColor=colors.HexColor("#283593"),
        )
        normal = styles["Normal"]
        normal.fontSize = 10

        elements = []

        # Cabeçalho
        elements.append(Paragraph("TransLog", title_style))
        elements.append(Paragraph("Comprovante de Entrega", subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a237e")))
        elements.append(Spacer(1, 8 * mm))

        # Status e código
        status_color = "#2e7d32"  # verde para DELIVERED
        status_data = [
            ["Código de Rastreamento", "Status", "Data de Entrega"],
            [
                delivery.tracking_code,
                Paragraph(f'<font color="{status_color}"><b>ENTREGUE</b></font>', normal),
                _fmt_dt(delivery.delivered_at),
            ],
        ]
        status_table = Table(status_data, colWidths=["40%", "20%", "40%"])
        status_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#283593")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5cae9")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(status_table)
        elements.append(Spacer(1, 6 * mm))

        # Destinatário
        elements.append(Paragraph("Destinatário", section_style))
        recipient_data = [
            ["Nome", delivery.recipient_name or "—"],
            ["Email", delivery.recipient_email or "—"],
            ["Telefone", delivery.recipient_phone or "—"],
        ]
        recipient_table = Table(recipient_data, colWidths=["30%", "70%"])
        recipient_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5cae9")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(recipient_table)
        elements.append(Spacer(1, 4 * mm))

        # Endereços
        elements.append(Paragraph("Endereços", section_style))
        address_data = [
            ["Origem", delivery.origin_address],
            ["Destino", delivery.destination_address],
        ]
        address_table = Table(address_data, colWidths=["20%", "80%"])
        address_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5cae9")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(address_table)
        elements.append(Spacer(1, 4 * mm))

        # Detalhes da carga
        elements.append(Paragraph("Detalhes da Carga", section_style))
        cargo_data = [
            ["Descrição", delivery.description or "—"],
            ["Peso (kg)", _fmt_float(delivery.weight_kg)],
            ["Valor declarado (R$)", _fmt_float(delivery.value)],
            ["Observações", delivery.delivery_notes or "—"],
        ]
        cargo_table = Table(cargo_data, colWidths=["30%", "70%"])
        cargo_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5cae9")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(cargo_table)
        elements.append(Spacer(1, 4 * mm))

        # Linha do tempo
        elements.append(Paragraph("Linha do Tempo", section_style))
        timeline_data = [
            ["Evento", "Data/Hora"],
            ["Criação", _fmt_dt(delivery.created_at)],
            ["Aceite", _fmt_dt(delivery.accepted_at)],
            ["Coleta", _fmt_dt(delivery.picked_up_at)],
            ["Entrega", _fmt_dt(delivery.delivered_at)],
        ]
        timeline_table = Table(timeline_data, colWidths=["40%", "60%"])
        timeline_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#283593")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5cae9")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(timeline_table)
        elements.append(Spacer(1, 4 * mm))

        # Autorização manual (se aplicável)
        if delivery.manually_authorized:
            elements.append(Paragraph("Autorização Manual", section_style))
            elements.append(Paragraph(
                "Esta entrega foi autorizada manualmente por um operador/administrador.",
                normal,
            ))
            elements.append(Spacer(1, 4 * mm))

        # Rodapé
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#9fa8da")))
        elements.append(Spacer(1, 4 * mm))
        generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M") + " UTC"
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        )
        elements.append(Paragraph(
            f"Documento gerado em {generated_at} | TransLog — Sistema de Gestão de Entregas",
            footer_style,
        ))

        doc.build(elements)
        buffer.seek(0)
        return buffer.read()
