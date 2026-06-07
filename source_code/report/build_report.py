from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "application" / "Mahjong_RL_Project_Report.pdf"


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=14) for item in items],
        bulletType="bullet",
        leftIndent=18,
    )


def build():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            textColor=colors.HexColor("#5c6761"),
            fontSize=9,
            leading=12,
        )
    )
    styles["Title"].fontSize = 24
    styles["Heading1"].spaceBefore = 14
    styles["Heading1"].spaceAfter = 8
    styles["BodyText"].leading = 14

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=LETTER,
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
    )

    story = [
        Paragraph("Mahjong Reinforcement Learning Agent", styles["Title"]),
        Paragraph("IEMS5726AB Data Science in Practice Project Report Draft", styles["SmallMuted"]),
        Spacer(1, 0.25 * inch),
        Paragraph("1. Problem Definition", styles["Heading1"]),
        Paragraph(
            "This project develops a browser-playable Japanese mahjong demonstration in which a human player competes against two random baseline agents and one reinforcement-learning agent slot based on Mortal. The application aims to make an RL mahjong policy observable: users can inspect each player's hand/discards, follow the event log, and see the RL agent's discard reasoning and action-value scores.",
            styles["BodyText"],
        ),
        Paragraph("2. Data Science Pipeline", styles["Heading1"]),
        bullets(
            [
                "Data collection: Mortal supports mjai/Tenhou-style mahjong records, typically stored as compressed JSON log files.",
                "Preprocessing and representation: game events are converted into player observations and legal-action masks by Mortal's libriichi environment.",
                "Modeling: Mortal uses a residual neural network encoder and DQN action-value heads to select legal mahjong actions.",
                "Inference: the project includes a Python CLI adapter that can call Mortal's documented `mortal.py <player_id>` interface when a trained checkpoint is configured.",
                "Fallback demonstration: because model weights should not be shipped inside the source archive, the browser demo uses a deterministic Mortal-inspired value policy when the checkpoint is unavailable.",
            ],
            styles["BodyText"],
        ),
        Paragraph("3. System Architecture and UI/UX", styles["Heading1"]),
        Table(
            [
                ["Layer", "Implementation", "Purpose"],
                ["Source model", "Mortal-for-mahjong/Mortal", "Training, observation encoding, DQN model, and CLI inference"],
                ["Agent adapter", "source_code/mahjong_agent/agent.py", "Loads Mortal CLI when possible and falls back to an explainable policy"],
                ["Application", "application/index.html, styles.css, app.js", "Playable mahjong demo with human, random agents, and RL agent"],
                ["Submission metadata", "application/model_link.txt", "External checkpoint link placeholder required by course instruction"],
            ],
            colWidths=[1.35 * inch, 2.25 * inch, 2.8 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6b57")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d2dad5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Spacer(1, 0.12 * inch),
        Paragraph(
            "The UI is designed for the short demonstration video: the first screen is the actual mahjong table, with controls for starting a new round and advancing agents. The side panel explains the latest RL decision through ranked action values instead of hiding the model behind a black box.",
            styles["BodyText"],
        ),
        PageBreak(),
        Paragraph("4. Challenges", styles["Heading1"]),
        bullets(
            [
                "Mortal requires trained checkpoints and compiled dependencies; the project separates source code from model weights and documents how to connect the external checkpoint.",
                "A full mahjong engine is complex, so the demo focuses on the course-required human-vs-agent interaction loop and makes draw/discard decisions clear.",
                "To keep the demo reliable for grading, the RL slot has an explainable deterministic fallback when the model file is unavailable.",
                "The interface must be understandable in a short video, so the page emphasizes visible table state, event history, and action-value visualization.",
            ],
            styles["BodyText"],
        ),
        Paragraph("5. References", styles["Heading1"]),
        bullets(
            [
                "Equim-chan, Mortal: https://github.com/Equim-chan/Mortal",
                "Mortal documentation and mjai inference example: https://mortal.ekyu.moe",
                "ReportLab for generating this PDF draft: https://www.reportlab.com",
            ],
            styles["BodyText"],
        ),
        Paragraph("6. VeriGuide Receipt", styles["Heading1"]),
        Paragraph(
            "Attach the signed VeriGuide receipt before final submission. Only one group member needs to submit the report to VeriGuide according to the project instructions.",
            styles["BodyText"],
        ),
    ]

    doc.build(story)


if __name__ == "__main__":
    build()
