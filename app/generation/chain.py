from __future__ import annotations

from langchain.rate_limiters import BaseRateLimiter
from langchain_core.runnables import RunnableLambda 
from langchain_core.output_parsers import StrOutputParser

from llm_v2 import llm
from prompts import widerspruch_body_prompt
from rag.v2.retriever import 

chain = widerspruch_body_prompt(), retriever | llm | StrOutputParser()

