
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class Response(BaseModel):
    text: str
    confidence: int
    tokens: int
    