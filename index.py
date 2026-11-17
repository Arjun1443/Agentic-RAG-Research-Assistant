from pathlib import Path
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
ONNXMiniLM_L6_V2.DOWNLOAD_PATH = Path("/tmp/research-assistant/onnx-model")
from fastapi_app.main import app
