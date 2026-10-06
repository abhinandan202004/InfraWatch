"""Best-effort integrations. Failures are logged, never break the request."""
import json
import logging
import smtplib
from email.message import EmailMessage

import httpx

from .config import settings

log = logging.getLogger("infrawatch")

# ---------------- Kafka ----------------
_producer = None


def _get_producer():
    global _producer
    if _producer is None and settings.kafka_enabled:
        try:
            from confluent_kafka import Producer

            _producer = Producer({"bootstrap.servers": settings.kafka_bootstrap, "socket.timeout.ms": 3000,
                                  "message.timeout.ms": 5000})
        except Exception as e:  # noqa: BLE001
            log.warning("Kafka unavailable: %s", e)
    return _producer


def publish(topic: str, key: str, payload: dict) -> None:
    p = _get_producer()
    if not p:
        return
    try:
        p.produce(topic, key=key, value=json.dumps(payload, default=str))
        p.poll(0)
    except Exception as e:  # noqa: BLE001
        log.warning("Kafka publish failed: %s", e)


# ---------------- ZincSearch ----------------
_AUTH = lambda: (settings.zinc_user, settings.zinc_password)  # noqa: E731


def index_doc(index: str, doc_id: str, doc: dict) -> None:
    try:
        httpx.put(f"{settings.zinc_url}/api/{index}/_doc/{doc_id}", json=doc, auth=_AUTH(), timeout=3)
    except Exception as e:  # noqa: BLE001
        log.warning("Zinc index failed: %s", e)


def search_ids(index: str, query: str, limit: int = 50) -> list[str] | None:
    """Return matching doc ids, or None if Zinc is unreachable (caller falls back to SQL)."""
    try:
        r = httpx.post(
            f"{settings.zinc_url}/api/{index}/_search",
            json={"search_type": "querystring", "query": {"term": query}, "max_results": limit},
            auth=_AUTH(),
            timeout=3,
        )
        r.raise_for_status()
        return [h["_id"] for h in r.json()["hits"]["hits"]]
    except Exception as e:  # noqa: BLE001
        log.warning("Zinc search failed: %s", e)
        return None


# ---------------- Email ----------------
def send_mail(to: list[str], cc: list[str], subject: str, body: str, thread_id: str) -> None:
    if not to:
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{thread_id}.{abs(hash(subject + body))}@infrawatch>"
    msg["In-Reply-To"] = f"<{thread_id}@infrawatch>"
    msg["References"] = f"<{thread_id}@infrawatch>"
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
            s.send_message(msg, to_addrs=to + cc)
    except Exception as e:  # noqa: BLE001
        log.warning("SMTP send failed: %s", e)
