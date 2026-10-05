import hashlib
import io
import json
import logging
import os
from urllib.parse import unquote

# Hugging Face needs a writable cache. /tmp is always writable on Functions.
os.environ.setdefault("HF_HOME", "/tmp/hf")

import azure.functions as func
from azure.identity import DefaultAzureCredential

app = func.FunctionApp()

COSMOS_ENDPOINT = "https://documind-cosmos-nna2005.documents.azure.com:443/"
APPCONFIG_ENDPOINT = "https://documind-appconfig-nna2005.azconfig.io"
DATABASE_NAME = "documind-db"
CONTAINER_NAME = "documents-vector"
MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dimensions, matches the vector policy
MAX_TEXT_BYTES = 1_500_000        # Cosmos items are capped at 2 MB

_credential = None
_container = None
_model = None
_telemetry_done = False


def _get_credential():
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def _init_telemetry():
    """Best effort: missing telemetry must not stop document processing."""
    global _telemetry_done
    if _telemetry_done:
        return
    _telemetry_done = True
    try:
        from azure.appconfiguration.provider import load
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.sdk.resources import Resource

        config = load(endpoint=APPCONFIG_ENDPOINT, credential=_get_credential(),keyvault_credential=_get_credential())
        configure_azure_monitor(
            connection_string=config["DocuMind:AppInsightsConnectionString"],
            resource=Resource.create({"service.name": "documind-func"}),
        )
        logging.info("Telemetry initialised.")
    except Exception:
        logging.exception("Telemetry setup failed; continuing without it.")


def _get_container():
    """Created on first use. Failures raise, so they show up on the message that hit them."""
    global _container
    if _container is None:
        from azure.cosmos import CosmosClient

        client = CosmosClient(COSMOS_ENDPOINT, credential=_get_credential())
        container = client.get_database_client(DATABASE_NAME).get_container_client(CONTAINER_NAME)
        container.read()  # fails fast on auth errors or a wrong name
        _container = container
        logging.info("Cosmos container ready.")
    return _container


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logging.info("Loading embedding model %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logging.info("Embedding model loaded.")
    return _model


def _extract_blob_urls(body: str):
    """Accepts one Event Grid event or CloudEvent, or a list of them."""
    payload = json.loads(body)
    events = payload if isinstance(payload, list) else [payload]
    urls = []
    for event in events:
        event_type = event.get("eventType") or event.get("type") or ""
        if event_type and not event_type.endswith("BlobCreated"):
            logging.info("Skipping event type %s", event_type)
            continue
        url = (event.get("data") or {}).get("url")
        if not url:
            logging.warning("Event has no data.url: %s", event)
            continue
        urls.append(url)
    return urls


def _process_blob(blob_url: str):
    from azure.storage.blob import BlobClient
    from pypdf import PdfReader

    file_name = unquote(blob_url.rsplit("/", 1)[-1])
    if not file_name.lower().endswith(".pdf"):
        logging.info("Skipping non-PDF blob %s", file_name)
        return

    logging.info("Step 1/4: downloading %s", file_name)
    blob_bytes = BlobClient.from_blob_url(blob_url, credential=_get_credential()).download_blob().readall()

    logging.info("Step 2/4: extracting text (%d bytes)", len(blob_bytes))
    reader = PdfReader(io.BytesIO(blob_bytes))
    text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if not text:
        # Retrying cannot fix a scanned or empty PDF, so complete the message.
        logging.warning("No extractable text in %s (scanned or empty PDF). Skipping.", file_name)
        return
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        text = text.encode("utf-8")[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
        logging.warning("Text of %s truncated to fit the Cosmos item size limit.", file_name)

    logging.info("Step 3/4: embedding %d characters", len(text))
    embedding = _get_model().encode(text).tolist()

    logging.info("Step 4/4: writing to Cosmos")
    document = {
        # Same blob gives the same id, so a retry overwrites instead of duplicating.
        "id": hashlib.sha256(blob_url.encode("utf-8")).hexdigest(),
        "userId": "default-user",
        "filename": file_name,
        "blobUrl": blob_url,
        "text": text,
        "embedding": embedding,
    }
    saved = _get_container().upsert_item(body=document)
    logging.info("Document %s stored with id %s", file_name, saved["id"])


@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="document-processing",
    connection="ServiceBusConnection",
)
def process_document(msg: func.ServiceBusMessage):
    _init_telemetry()

    body = msg.get_body().decode("utf-8")
    logging.info("Message %s (delivery %s): %s", msg.message_id, msg.delivery_count, body)

    try:
        urls = _extract_blob_urls(body)
    except json.JSONDecodeError:
        # A malformed message will never succeed, so do not retry it.
        logging.error("Message body is not JSON; discarding: %s", body)
        return

    if not urls:
        logging.warning("No blob URLs found in message.")
        return

    for url in urls:
        try:
            _process_blob(url)
        except Exception:
            logging.exception("Failed to process %s", url)
            raise  # let Service Bus retry, then dead-letter
