import os
import json
import shutil
from typing import Optional, Dict, Any, List, Callable
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from vanna.openai import OpenAI_Chat
from vanna.chromadb import ChromaDB_VectorStore
import openai
import httpx

from app.models.vanna_models import VannaConfig, DatabaseConfig, VannaTrainingData
from app.models.database import Connection, ConnectionStatus
from app.config import settings
from app.core.vanna_wrapper import MyVanna
from app.models.database import User

logger = logging.getLogger(__name__)


class VannaService:
    """Service for managing Vanna AI instances and training with user context"""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR
    
    async def setup_and_train_vanna(
        self, 
        connection_id: str, 
        db_config: DatabaseConfig, 
        vanna_config: VannaConfig,
        retrain: bool = True,
        progress_callback: Optional[callable] = None,
        user: Optional[User] = None
    ) -> Optional[MyVanna]:
        """Setup and train Vanna instance with optional user context"""
        
        try:
            user_info = f" for user {user.email}" if user else ""
            logger.info(f"Starting Vanna setup for connection {connection_id}{user_info}")
            
            if progress_callback:
                await progress_callback(10, "Initializing Vanna instance...")
            
            # ChromaDB directory
            chromadb_dir = os.path.join(self.data_dir, "connections", connection_id, "chromadb_store")
            
            # Clear existing ChromaDB if retraining
            if retrain and os.path.exists(chromadb_dir):
                if progress_callback:
                    await progress_callback(15, "Clearing existing training data...")
                shutil.rmtree(chromadb_dir)
                logger.info(f"Cleared existing ChromaDB for connection {connection_id}{user_info}")
            
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
            
            logger.info(f"Vanna connected to database for connection {connection_id}{user_info}")
            
            # Load and train with data
            if retrain:
                await self._train_vanna_instance(vn, connection_id, progress_callback, user)
            
            if progress_callback:
                await progress_callback(100, "Vanna setup and training completed")
            
            logger.info(f"Vanna setup completed successfully for connection {connection_id}{user_info}")
            return vn
            
        except Exception as e:
            error_msg = f"Failed to setup Vanna for connection {connection_id}{user_info}: {e}"
            logger.error(error_msg)
            if progress_callback:
                await progress_callback(0, f"Setup failed: {str(e)}")
            return None
    
    async def _train_vanna_instance(
        self, 
        vn: MyVanna, 
        connection_id: str, 
        progress_callback: Optional[callable] = None,
        user: Optional[User] = None
    ):
        """Train Vanna instance with generated data"""
        
        user_info = f" for user {user.email}" if user else ""
        
        # Load training data
        training_data_path = os.path.join(
            self.data_dir, "connections", connection_id, "generated_training_data.json"
        )
        
        if not os.path.exists(training_data_path):
            raise FileNotFoundError(f"Training data not found for connection {connection_id}. Please generate data first.")
        
        if progress_callback:
            await progress_callback(30, "Loading training data...")
        
        try:
            with open(training_data_path, 'r') as f:
                training_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load training data: {e}")
        
        documentation = training_data.get('documentation', [])
        examples = training_data.get('examples', [])
        
        # Log training info with user context
        logger.info(f"Training Vanna with {len(documentation)} docs and {len(examples)} examples for connection {connection_id}{user_info}")
        
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
        
        logger.info(f"Vanna training completed for connection {connection_id}{user_info}")
    
    def get_vanna_instance(
        self, 
        connection_id: str, 
        db_config: DatabaseConfig, 
        vanna_config: VannaConfig,
        user: Optional[User] = None
    ) -> Optional[MyVanna]:
        """Get existing Vanna instance (no caching - always create fresh)"""
        
        user_info = f" for user {user.email}" if user else ""
        
        try:
            # Check if ChromaDB exists
            chromadb_dir = os.path.join(self.data_dir, "connections", connection_id, "chromadb_store")
            
            if not os.path.exists(chromadb_dir):
                logger.warning(f"No trained model found for connection {connection_id}{user_info}")
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
            
            logger.info(f"Vanna instance loaded successfully for connection {connection_id}{user_info}")
            return vn
            
        except Exception as e:
            logger.error(f"Failed to get Vanna instance for connection {connection_id}{user_info}: {e}")
            return None
    
    def validate_user_access_to_connection(
        self, 
        connection_id: str, 
        user: User
    ) -> bool:
        """Validate that user has access to the connection's Vanna model"""
        try:
            chromadb_dir = os.path.join(self.data_dir, "connections", connection_id, "chromadb_store")
            
            if not os.path.exists(chromadb_dir):
                logger.warning(f"No Vanna model found for connection {connection_id}")
                return False
            
            # Check if training data includes user info (for connections created after user system)
            training_data_path = os.path.join(self.data_dir, "connections", connection_id, "generated_training_data.json")
            
            if os.path.exists(training_data_path):
                try:
                    with open(training_data_path, 'r') as f:
                        training_data = json.load(f)
                    
                    # If training data has user_id, verify it matches
                    if 'user_id' in training_data:
                        return training_data['user_id'] == str(user.id)
                    
                except Exception as e:
                    logger.warning(f"Could not validate training data ownership: {e}")
            
            # For legacy connections without user info in training data, allow access
            # The connection ownership will be verified at the database level
            return True
            
        except Exception as e:
            logger.error(f"Error validating user access to connection {connection_id}: {e}")
            return False
    
    def cleanup_connection_model(self, connection_id: str, user: Optional[User] = None) -> bool:
        """Clean up Vanna model files for a connection"""
        user_info = f" for user {user.email}" if user else ""
        
        try:
            chromadb_dir = os.path.join(self.data_dir, "connections", connection_id, "chromadb_store")
            
            if os.path.exists(chromadb_dir):
                shutil.rmtree(chromadb_dir)
                logger.info(f"Cleaned up Vanna model for connection {connection_id}{user_info}")
            
            training_data_path = os.path.join(self.data_dir, "connections", connection_id, "generated_training_data.json")
            if os.path.exists(training_data_path):
                os.remove(training_data_path)
                logger.info(f"Cleaned up training data for connection {connection_id}{user_info}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup Vanna model for connection {connection_id}{user_info}: {e}")
            return False

# Global vanna service instance
vanna_service = VannaService()