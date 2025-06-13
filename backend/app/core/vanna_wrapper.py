import os
import json
import shutil
from typing import Optional, Dict, Any, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from vanna.openai import OpenAI_Chat
from vanna.chromadb import ChromaDB_VectorStore
import openai
import httpx

from app.models.vanna_models import VannaConfig, DatabaseConfig, VannaTrainingData
from app.models.database import User
from app.config import settings

logger = logging.getLogger(__name__)

class MyVanna(OpenAI_Chat, ChromaDB_VectorStore):
    """Custom Vanna implementation for MS SQL Server"""
    
    def __init__(self, config=None):
        # Initialize OpenAI client
        client = openai.OpenAI(
            base_url=config.get("base_url", settings.OPENAI_BASE_URL),
            api_key=config.get("api_key", settings.OPENAI_API_KEY),
            http_client=httpx.Client(verify=False)
        )
        
        OpenAI_Chat.__init__(self, config=config, client=client)
        ChromaDB_VectorStore.__init__(self, config=config)
    
    def get_sql_prompt(
        self,
        initial_prompt: str,
        question: str,
        question_sql_list: list,
        ddl_list: list,
        doc_list: list,
        **kwargs,
    ):
        """Custom SQL prompt for MS SQL Server"""
        
        if initial_prompt is None:
            initial_prompt = f"You are a {self.dialect} expert. " + \
            "Please help to generate a SQL query to answer the question. Your response should ONLY be based on the given context and follow the response guidelines and format instructions. "

        initial_prompt = self.add_ddl_to_prompt(
            initial_prompt, ddl_list, max_tokens=self.max_tokens
        )

        if self.static_documentation != "":
            doc_list.append(self.static_documentation)

        initial_prompt = self.add_documentation_to_prompt(
            initial_prompt, doc_list, max_tokens=self.max_tokens
        )

        initial_prompt += (
            "===Response Guidelines \n"
            "1. If the provided context is sufficient, please generate a valid SQL query without any explanations for the question. \n"
            "2. If the provided context is almost sufficient but requires knowledge of a specific string in a particular column, please generate an intermediate SQL query to find the distinct strings in that column. Prepend the query with a comment saying intermediate_sql \n"
            "3. If the provided context is insufficient, please explain why it can't be generated. \n"
            "4. Please use the most relevant table(s). \n"
            "5. If the question has been asked and answered before, please repeat the answer exactly as it was given before. \n"
            f"6. Ensure that the output SQL is {self.dialect}-compliant and executable, and free of syntax errors. \n"
        )

        message_log = [self.system_message(initial_prompt)]

        for example in question_sql_list:
            if example is not None and "question" in example and "sql" in example:
                message_log.append(self.user_message(example["question"]))
                message_log.append(self.assistant_message(example["sql"]))

        if history := kwargs.get("chat_history"):
            for h in history:
                if h["role"] == "assistant":
                    message_log.append(self.assistant_message(h["content"]))
                elif h["role"] == "user":
                    message_log.append(self.user_message(h["content"]))

        message_log.append(self.user_message(question))

        return message_log
