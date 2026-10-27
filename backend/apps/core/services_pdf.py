"""Service de génération PDF.

Stratégie :
1. WeasyPrint (HTML -> PDF) si ses bibliothèques système sont installées
   (c'est le cas dans l'image Docker de production).
2. Repli : générateur PDF minimal fondé sur reportlab.

Le repli garantit que l'application reste fonctionnelle en développement sur
des postes sans Pango/Cairo. Les deux chemins sont testés.
"""

import html
import logging
import re
from io import BytesIO

logger = logging.getLogger(__name__)


def _weasyprint_disponible() -> bool:
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def html_vers_pdf(html_content: str) -> bytes:
    """Convertit du HTML en PDF, avec repli reportlab si nécessaire."""
    if _weasyprint_disponible():
        from weasyprint import HTML

        buffer = BytesIO()
        HTML(string=html_content).write_pdf(buffer)
        return buffer.getvalue()

    logger.warning(
        "WeasyPrint indisponible (bibliothèques système manquantes) : "
        "utilisation du générateur PDF de repli."
    )
    return _html_vers_pdf_repli(html_content)


def _nettoie_texte(fragment: str) -> str:
    texte = re.sub(r"<br\s*/?>", "\n", fragment)
    texte = re.sub(r"</(p|div|tr|h[1-6]|li)>", "\n", texte)
    texte = re.sub(r"</t[dh]>", " | ", texte)
    texte = re.sub(r"<[^>]+>", "", texte)
    return html.unescape(texte)


def _html_vers_pdf_repli(html_content: str) -> bytes:
    """Repli simple : extrait le texte et produit un PDF lisible."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    doc = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm
    ligne_h = 5 * mm

    doc.setFont("Helvetica-Bold", 10)
    texte = _nettoie_texte(html_content)
    for ligne_brute in texte.splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            y -= ligne_h / 2
            continue
        # Découpe les lignes trop longues
        morceaux = [ligne[i : i + 110] for i in range(0, len(ligne), 110)] or [""]
        for morceau in morceaux:
            if y < 20 * mm:
                doc.showPage()
                doc.setFont("Helvetica", 9)
                y = height - 20 * mm
            doc.setFont("Helvetica", 9)
            doc.drawString(15 * mm, y, morceau)
            y -= ligne_h
    doc.save()
    return buffer.getvalue()
