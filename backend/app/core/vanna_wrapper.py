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

class VannaService:
    """Service for managing Vanna AI instances and training"""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR
    
    async def setup_and_train_vanna(
        self, 
        connection_id: str, 
        db_config: DatabaseConfig, 
        vanna_config: VannaConfig,
        retrain: bool = True,
        progress_callback: Optional[callable] = None
    ) -> Optional[MyVanna]:
        """Setup and train Vanna instance"""
        
        try:
            if progress_callback:
                await progress_callback(10, "Initializing Vanna instance...")
            
            # ChromaDB directory
            chromadb_dir = os.path.join(self.data_dir, "connections", connection_id, "chromadb_store")
            
            # Clear existing ChromaDB if retraining
            if retrain and os.path.exists(chromadb_dir):
                if progress_callback:
                    await progress_callback(15, "Clearing existing training data...")
                shutil.rmtree(chromadb_dir)
                logger.info(f"Cleared existing ChromaDB for connection {connection_id}")
            
            # Initialize Vanna
            vn = MyVanna(config={
                "api_key": vanna_config.api_key,
                "base_url": vanna_config.base_url,
                "model": vanna_config.model,
                "path": chromadb_dir
            })
            
            if progress_callback:
                await progress_callback(25, "Connecting to database...")
            
            # Connect to database
            odbc_conn_str = db_config.to_odbc_connection_string()
            vn.connect_to_mssql(odbc_conn_str=odbc_conn_str)
            
            logger.info(f"Vanna connected to database for connection {connection_id}")
            
            # Load and train with data
            if retrain:
                await self._train_vanna_instance(vn, connection_id, progress_callback)
            
            if progress_callback:
                await progress_callback(100, "Vanna setup and training completed")
            
            return vn
            
        except Exception as e:
            logger.error(f"Failed to setup Vanna for connection {connection_id}: {e}")
            if progress_callback:
                await progress_callback(0, f"Setup failed: {str(e)}")
            return None
    
    async def _train_vanna_instance(
        self, 
        vn: MyVanna, 
        connection_id: str, 
        progress_callback: Optional[callable] = None
    ):
        """Train Vanna instance with generated data"""
        
        # Load training data
        training_data_path = os.path.join(
            self.data_dir, "connections", connection_id, "generated_training_data.json"
        )
        
        if not os.path.exists(training_data_path):
            raise FileNotFoundError("Training data not found. Please generate data first.")
        
        if progress_callback:
            await progress_callback(30, "Loading training data...")
        
        with open(training_data_path, 'r') as f:
            training_data = json.load(f)
        
        documentation = training_data.get('documentation', [])
        examples = training_data.get('examples', [])
        
        total_items = len(documentation) + len(examples)
        current_item = 0
        
        if progress_callback:
            await progress_callback(40, f"Training with {len(documentation)} documentation entries...")
        
        # Train with documentation
        for doc_entry in documentation:
            content = doc_entry.get('content')
            if content:
                vn.train(documentation=content)
                current_item += 1
                progress = 40 + int((current_item / total_items) * 40)
                if progress_callback:
                    await progress_callback(progress, f"Training documentation: {doc_entry.get('doc_type', 'unknown')}")
        
        if progress_callback:
            await progress_callback(80, f"Training with {len(examples)} examples...")
        
        # Train with examples
        for example_entry in examples:
            question = example_entry.get('question')
            sql = example_entry.get('sql')
            if question and sql:
                vn.train(question=question, sql=sql)
                current_item += 1
                progress = 40 + int((current_item / total_items) * 40)
                if progress_callback:
                    await progress_callback(progress, f"Training example: {question[:50]}...")
        
        if progress_callback:
            await progress_callback(95, "Training completed, saving model...")
        
        logger.info(f"Vanna training completed for connection {connection_id}")
    
    def get_vanna_instance(
        self, 
        connection_id: str, 
        db_config: DatabaseConfig, 
        vanna_config: VannaConfig
    ) -> Optional[MyVanna]:
        """Get existing Vanna instance (no caching - always create fresh)"""
        
        try:
            # Check if ChromaDB exists
            chromadb_dir = os.path.join(self.data_dir, "connections", connection_id, "chromadb_store")
            
            if not os.path.exists(chromadb_dir):
                logger.warning(f"No trained model found for connection {connection_id}")
                return None
            
            # Create fresh instance
            vn = MyVanna(config={
                "api_key": vanna_config.api_key,
                "base_url": vanna_config.base_url,
                "model": vanna_config.model,
                "path": chromadb_dir
            })
            
            # Connect to database
            odbc_conn_str = db_config.to_odbc_connection_string()
            vn.connect_to_mssql(odbc_conn_str=odbc_conn_str)
            
            return vn
            
        except Exception as e:
            logger.error(f"Failed to get Vanna instance for connection {connection_id}: {e}")
            return None

# Global vanna service instance
vanna_service = VannaService()