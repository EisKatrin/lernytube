"""Router für den KI-Lehrer und das automatisch sortierte Lernbuch.

Beantwortet Fragen wie ein Lehrer und ordnet Frage und Antwort
anschließend selbstständig in einen Themenbaum (das "Lernbuch") ein.
Vorerst nur für einen einzelnen, fest hinterlegten Benutzer freigeschaltet.
"""

import json
import os
import re
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from models import TutorAsk, TutorEntryOut, TutorTopicNode
from auth_utils import get_current_user_id

router = APIRouter()

ANTHROPIC_MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT_TEMPLATE = """Du bist ein geduldiger, fachkundiger Lehrer in der Lernplattform LernyTube. \
Die Nutzerin stellt dir eine Frage. Beantworte sie gründlich, verständlich und auf Deutsch, so wie ein \
guter Lehrer erklären würde: klar strukturiert, mit Beispielen wo hilfreich, aber ohne unnötige Länge.

Danach ordnest du die Frage in ein Lernbuch ein, das nach Themen und Unterthemen sortiert ist. \
Das sind die bereits vorhandenen Themenpfade (Format "Oberthema > Unterthema"):
{existing_topics}

Wähle einen passenden bestehenden Pfad ODER erstelle einen neuen (ggf. als neues Unterthema zu einem \
bestehenden Oberthema). Maximal zwei Ebenen tief. Wenn du ein bestehendes Thema wiederverwendest, \
schreibe seinen Titel exakt wie oben angegeben.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, ohne Markdown-Codeblock und ohne weiteren Text, \
exakt in diesem Format:
{{"answer": "<deine vollständige Antwort als Markdown-Text>", "topic_path": ["Oberthema", "Unterthema"]}}

Das Feld "topic_path" darf auch nur ein Element enthalten, wenn kein Unterthema sinnvoll ist."""


async def require_tutor_access(user_id: str = Depends(get_current_user_id)) -> str:
    """FastAPI-Abhängigkeit: Erlaubt den Zugriff nur für den freigeschalteten Benutzer.

    Args:
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Die Benutzer-ID, wenn der Zugriff erlaubt ist.

    Raises:
        HTTPException: 403, wenn der Benutzer nicht freigeschaltet ist.
    """
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    allowed_username = os.environ.get("TUTOR_ALLOWED_USERNAME", "EisKatrin")
    if not user or user.get("username") != allowed_username:
        raise HTTPException(status_code=403, detail="Diese Funktion ist aktuell nicht verfügbar.")
    return user_id


async def _load_topic_paths(db, user_id: str) -> list[str]:
    """Baut aus allen Themen des Benutzers eine flache Liste von Pfad-Strings.

    Args:
        db: Die Datenbankinstanz.
        user_id: Die Benutzer-ID.

    Returns:
        Sortierte, eindeutige Liste von Pfaden im Format "Oberthema > Unterthema".
    """
    topics = await db.topics.find({"user_id": user_id}).to_list(length=500)
    by_id = {str(t["_id"]): t for t in topics}
    paths = []
    for t in topics:
        chain = [t["title"]]
        parent_id = t.get("parent_id")
        while parent_id and parent_id in by_id:
            parent = by_id[parent_id]
            chain.insert(0, parent["title"])
            parent_id = parent.get("parent_id")
        paths.append(" > ".join(chain))
    return sorted(set(paths))


def _parse_tutor_response(text: str) -> dict:
    """Parst die JSON-Antwort des Lehrer-Modells robust.

    Args:
        text: Der rohe Textinhalt der Modellantwort.

    Returns:
        Ein Dict mit den Schlüsseln "answer" und "topic_path".
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            answer = str(obj.get("answer", "")).strip()
            path = [str(p).strip() for p in (obj.get("topic_path") or []) if str(p).strip()][:2]
            if answer and path:
                return {"answer": answer, "topic_path": path}
        except (json.JSONDecodeError, TypeError):
            pass
    # Fallback: Modell hat kein valides JSON geliefert — Rohtext trotzdem sichern
    return {"answer": text.strip() or "Keine Antwort erhalten.", "topic_path": ["Sonstiges"]}


async def _ask_claude(question: str, existing_paths: list[str]) -> dict:
    """Stellt die Frage an Claude und lässt Antwort + Themenzuordnung liefern.

    Args:
        question: Die Frage der Nutzerin.
        existing_paths: Bereits vorhandene Themenpfade für konsistente Einsortierung.

    Returns:
        Ein Dict mit "answer" (str) und "topic_path" (list[str]).

    Raises:
        HTTPException: 500 wenn kein API-Key konfiguriert ist, 502 bei Fehlern der Anthropic-API.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="KI-Lehrer ist nicht konfiguriert (fehlender API-Key)")

    topics_text = "\n".join(f"- {p}" for p in existing_paths) if existing_paths else "(noch keine Themen vorhanden)"
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(existing_topics=topics_text)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": [{"role": "user", "content": question}],
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"KI-Lehrer nicht erreichbar (Status {resp.status_code})")

    data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    return _parse_tutor_response(text)


async def _find_or_create_topic_path(db, user_id: str, path: list[str]) -> tuple[str, list[str]]:
    """Findet oder erstellt entlang eines Themenpfads die zugehörigen Themen-Dokumente.

    Args:
        db: Die Datenbankinstanz.
        user_id: Die Benutzer-ID.
        path: Der Themenpfad, z.B. ["Programmieren", "Python"].

    Returns:
        Ein Tupel aus (ID des Blatt-Themas, tatsächlich verwendeter Pfad).
    """
    parent_id: str | None = None
    resolved_path = []
    topic_id = ""
    for title in path:
        query = {
            "user_id": user_id,
            "parent_id": parent_id,
            "title": {"$regex": f"^{re.escape(title)}$", "$options": "i"},
        }
        existing = await db.topics.find_one(query)
        if existing:
            topic_id = str(existing["_id"])
            resolved_path.append(existing["title"])
        else:
            doc = {
                "user_id": user_id,
                "parent_id": parent_id,
                "title": title,
                "created_at": datetime.now(timezone.utc),
            }
            result = await db.topics.insert_one(doc)
            topic_id = str(result.inserted_id)
            resolved_path.append(title)
        parent_id = topic_id
    return topic_id, resolved_path


@router.post("/ask", response_model=TutorEntryOut, status_code=status.HTTP_201_CREATED)
async def ask_tutor(data: TutorAsk, user_id: str = Depends(require_tutor_access)):
    """Stellt dem KI-Lehrer eine Frage und speichert Frage + Antwort einsortiert im Lernbuch.

    Args:
        data: Die gestellte Frage.
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Der neu erstellte Lernbuch-Eintrag inklusive Themenpfad.
    """
    db = get_db()
    question = data.question.strip()
    existing_paths = await _load_topic_paths(db, user_id)
    result = await _ask_claude(question, existing_paths)
    topic_id, resolved_path = await _find_or_create_topic_path(db, user_id, result["topic_path"])

    now = datetime.now(timezone.utc)
    entry_doc = {
        "user_id": user_id,
        "topic_id": topic_id,
        "question": question,
        "answer": result["answer"],
        "created_at": now,
    }
    insert_result = await db.qa_entries.insert_one(entry_doc)

    return TutorEntryOut(
        id=str(insert_result.inserted_id),
        topic_id=topic_id,
        topic_path=resolved_path,
        question=question,
        answer=entry_doc["answer"],
        created_at=now,
    )


@router.get("/book", response_model=list[TutorTopicNode])
async def get_book(user_id: str = Depends(require_tutor_access)):
    """Gibt das komplette Lernbuch als verschachtelten Themenbaum zurück.

    Args:
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Die Liste der Oberthemen, jeweils mit ihren Unterthemen und Einträgen.
    """
    db = get_db()
    topics = await db.topics.find({"user_id": user_id}).sort("title", 1).to_list(length=1000)
    entries = await db.qa_entries.find({"user_id": user_id}).sort("created_at", 1).to_list(length=5000)

    entries_by_topic: dict[str, list] = {}
    for e in entries:
        entries_by_topic.setdefault(e["topic_id"], []).append(e)

    nodes: dict[str, TutorTopicNode] = {}
    for t in topics:
        tid = str(t["_id"])
        node_entries = [
            TutorEntryOut(
                id=str(e["_id"]),
                topic_id=tid,
                topic_path=[],
                question=e["question"],
                answer=e["answer"],
                created_at=e["created_at"],
            )
            for e in entries_by_topic.get(tid, [])
        ]
        nodes[tid] = TutorTopicNode(id=tid, title=t["title"], entries=node_entries, children=[])

    roots: list[TutorTopicNode] = []
    for t in topics:
        tid = str(t["_id"])
        parent_id = t.get("parent_id")
        if parent_id and parent_id in nodes:
            nodes[parent_id].children.append(nodes[tid])
        else:
            roots.append(nodes[tid])
    return roots


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: str, user_id: str = Depends(require_tutor_access)):
    """Löscht einen einzelnen Lernbuch-Eintrag.

    Args:
        entry_id: Die MongoDB-ID des Eintrags.
        user_id: Die Benutzer-ID aus dem JWT-Token (Zugriffsprüfung).

    Raises:
        HTTPException: 404, wenn der Eintrag nicht gefunden wird.
    """
    db = get_db()
    result = await db.qa_entries.delete_one({"_id": ObjectId(entry_id), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
