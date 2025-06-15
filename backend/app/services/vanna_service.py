import os
import json
import shutil
from typing import Optional, Dict, Any, List, Callable
import logging
from sqlalchemy.ext.asyncio import AsyncSession
import time
import stat
import gc

from app.models.vanna_models import VannaConfig, DatabaseConfig, VannaTrainingData
from app.models.database import Connection, ConnectionStatus
from app.config import settings
from app.core.vanna_wrapper import MyVanna
from app.models.database import User

logger = logging.getLogger(__name__)


class VannaService:
    """Stateless service for managing Vanna AI instances - no persistent connections"""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR
        # NO instance caching - everything is stateless
    
    def _get_chromadb_path(self, connection_id: str) -> str:
        """Get the ChromaDB path for a connection - always use timestamp for fresh training"""
        timestamp = int(time.time())
        return os.path.join(self.data_dir, "connections", connection_id, f"chromadb_store_{timestamp}")
    
    def _get_latest_chromadb_path(self, connection_id: str) -> str:
        """Get the latest ChromaDB path for querying"""
        connection_dir = os.path.join(self.data_dir, "connections", connection_id)
        if not os.path.exists(connection_dir):
            return None
            
        # Find the latest chromadb directory
        chromadb_dirs = []
        for item in os.listdir(connection_dir):
            if item.startswith('chromadb_store_'):
                try:
                    timestamp = int(item.split('_')[-1])
                    chromadb_dirs.append((timestamp, os.path.join(connection_dir, item)))
                except ValueError:
                    continue
        
        if not chromadb_dirs:
            return None
            
        # Return the latest one
        chromadb_dirs.sort(reverse=True)
        return chromadb_dirs[0][1]
    
    def _verify_clean_state(self, connection_id: str) -> bool:
        """Verify that ChromaDB is completely clean"""
        connection_dir = os.path.join(self.data_dir, "connections", connection_id)
        
        if not os.path.exists(connection_dir):
            return True
            
        # Check for any chromadb_store directories
        chromadb_dirs = [item for item in os.listdir(connection_dir) if item.startswith('chromadb_store')]
        
        if chromadb_dirs:
            logger.warning(f"Found {len(chromadb_dirs)} remaining ChromaDB directories: {chromadb_dirs}")
            return False
            
        logger.info(f"Verified clean state for connection {connection_id}")
        return True
    
    def _ensure_directory_writable(self, path: str) -> None:
        """Ensure directory exists and is writable with full permissions"""
        try:
            # Remove directory if it exists to start completely fresh
            if os.path.exists(path):
                logger.info(f"🔥 Removing existing directory for fresh start: {path}")
                shutil.rmtree(path)
            
            # Create new directory with full permissions
            os.makedirs(path, exist_ok=True)
            os.chmod(path, 0o777)  # Full permissions for all
            
            # Set umask to ensure new files are created with write permissions
            old_umask = os.umask(0o000)
            
            # Test write permissions
            test_file = os.path.join(path, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.chmod(test_file, 0o666)
            os.remove(test_file)
            
            # Restore umask
            os.umask(old_umask)
            
            logger.info(f"🔥 Directory confirmed writable with full permissions: {path}")
        except Exception as e:
            logger.error(f"Directory not writable: {path}, error: {e}")
            raise
    
    def _force_cleanup_chromadb(self, connection_id: str) -> None:
        """Force cleanup of ChromaDB - COMPLETE WIPE for fresh training"""
        connection_dir = os.path.join(self.data_dir, "connections", connection_id)
        
        if not os.path.exists(connection_dir):
            return
            
        try:
            logger.info(f"COMPLETE ChromaDB cleanup for connection {connection_id}")
            
            # Remove ALL chromadb_store directories (including timestamped ones)
            removed_count = 0
            for item in os.listdir(connection_dir):
                if item.startswith('chromadb_store'):
                    chromadb_path = os.path.join(connection_dir, item)
                    if os.path.isdir(chromadb_path):
                        logger.info(f"Removing ChromaDB directory: {item}")
                        
                        # Multiple cleanup strategies
                        attempts = [
                            self._cleanup_attempt_1,
                            self._cleanup_attempt_2, 
                            self._cleanup_attempt_3
                        ]
                        
                        for i, cleanup_func in enumerate(attempts, 1):
                            try:
                                cleanup_func(chromadb_path)
                                logger.info(f"ChromaDB cleanup successful on attempt {i} for {item}")
                                removed_count += 1
                                break
                            except Exception as e:
                                logger.warning(f"Cleanup attempt {i} failed for {item}: {e}")
                                if i < len(attempts):
                                    time.sleep(0.5)  # Brief pause between attempts
                                continue
                        else:
                            # If all attempts failed, create backup name
                            backup_path = f"{chromadb_path}_backup_{int(time.time())}"
                            os.rename(chromadb_path, backup_path)
                            logger.warning(f"Could not delete {item}, renamed to: {os.path.basename(backup_path)}")
            
            logger.info(f"Removed {removed_count} ChromaDB directories for connection {connection_id}")
            
            # Force garbage collection to release any Python references
            gc.collect()
            
        except Exception as e:
            logger.error(f"ChromaDB cleanup failed: {e}")
            raise
    
    def _cleanup_attempt_1(self, chromadb_path: str):
        """Cleanup attempt 1: Fix permissions and delete"""
        for root, dirs, files in os.walk(chromadb_path):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)
        shutil.rmtree(chromadb_path)
    
    def _cleanup_attempt_2(self, chromadb_path: str):
        """Cleanup attempt 2: More aggressive permissions"""
        for root, dirs, files in os.walk(chromadb_path):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o777)
            for f in files:
                os.chmod(os.path.join(root, f), 0o666)
        shutil.rmtree(chromadb_path)
    
    def _cleanup_attempt_3(self, chromadb_path: str):
        """Cleanup attempt 3: File by file deletion"""
        for root, dirs, files in os.walk(chromadb_path, topdown=False):
            for f in files:
                file_path = os.path.join(root, f)
                os.chmod(file_path, 0o666)
                os.remove(file_path)
            for d in dirs:
                dir_path = os.path.join(root, d)
                os.chmod(dir_path, 0o777)
                os.rmdir(dir_path)
        os.rmdir(chromadb_path)
    
    async def setup_and_train_vanna(
        self, 
        connection_id: str, 
        db_config: DatabaseConfig, 
        vanna_config: VannaConfig,
        retrain: bool = True,
        progress_callback: Optional[callable] = None,
        user: Optional[User] = None
    ) -> Optional[MyVanna]:
        """Setup and train Vanna instance - STATELESS, returns instance but doesn't cache it"""
        
        vanna_instance = None
        try:
            user_info = f" for user {user.email}" if user else ""
            logger.info(f"Starting Vanna setup for connection {connection_id}{user_info}")
            
            if progress_callback:
                await progress_callback(10, "Initializing Vanna instance...")
            
            # Get unique ChromaDB path for this training session
            chromadb_path = self._get_chromadb_path(connection_id)
            
            # Skip cleanup - just create a fresh directory with timestamp
            if progress_callback:
                await progress_callback(15, "Creating fresh ChromaDB directory...")
                
            logger.info(f"🔥 Using fresh ChromaDB path: {chromadb_path}")
            
            self._force_cleanup_chromadb(connection_id)

            # Ensure directory is ready
            if progress_callback:
                await progress_callback(20, "Setting up fresh ChromaDB directory...")
            self._ensure_directory_writable(chromadb_path)
            
            # Set ChromaDB environment variables for proper permissions
            os.environ['ANONYMIZED_TELEMETRY'] = 'False'
            os.environ['CHROMA_SERVER_AUTHN_PROVIDER'] = ''
            
            # Create completely fresh Vanna instance
            if progress_callback:
                await progress_callback(25, "Creating fresh Vanna instance...")
            
            # Create fresh config without unsupported parameters
            fresh_config = {
                "api_key": vanna_config.api_key,
                "base_url": vanna_config.base_url,
                "model": vanna_config.model,
                "path": chromadb_path
            }
            
            logger.info(f"🔥 Creating MyVanna with config: {fresh_config}")
            vanna_instance = MyVanna(config=fresh_config)
            
            # CRITICAL: Initialize ChromaDB properly by forcing a small test training
            try:
                logger.info(f"🔥 Initializing ChromaDB database tables...")
                
                # Set umask to ensure all files are created with write permissions
                old_umask = os.umask(0o000)
                
                # Force ChromaDB directory to be fully writable
                os.chmod(chromadb_path, 0o777)
                
                # Initialize with a simple documentation entry
                vanna_instance.train(documentation="ChromaDB initialization test")
                
                # Restore umask
                os.umask(old_umask)
                
                logger.info(f"🔥 ChromaDB initialization successful")
            except Exception as e:
                logger.error(f"🔥 ChromaDB initialization failed: {e}")
                # Try one more time with even more aggressive permissions
                try:
                    import subprocess
                    subprocess.run(['chmod', '-R', '777', chromadb_path], check=False)
                    vanna_instance.train(documentation="ChromaDB retry initialization")
                    logger.info(f"🔥 ChromaDB initialization successful on retry")
                except Exception as e2:
                    raise Exception(f"Failed to initialize ChromaDB after retry: {e2}")
            
            if progress_callback:
                await progress_callback(30, "Connecting to database...")
            
            # Connect to database
            odbc_conn_str = db_config.to_odbc_connection_string()
            vanna_instance.connect_to_mssql(odbc_conn_str=odbc_conn_str)
            
            logger.info(f"Vanna connected to database for connection {connection_id}{user_info}")
            
            # Load and train with data
            if retrain:
                await self._train_vanna_instance(vanna_instance, connection_id, progress_callback, user)
            
            if progress_callback:
                await progress_callback(100, "Vanna setup and training completed")
            
            logger.info(f"Vanna setup completed successfully for connection {connection_id}{user_info}")
            return vanna_instance
            
        except Exception as e:
            error_msg = f"Failed to setup Vanna for connection {connection_id}{user_info}: {e}"
            logger.error(error_msg, exc_info=True)
            
            # Clean up on failure
            if vanna_instance:
                try:
                    del vanna_instance
                    gc.collect()
                except:
                    pass
            
            if progress_callback:
                await progress_callback(0, f"Setup failed: {str(e)}")
            return None

    async def _train_vanna_instance(
        self, 
        vanna_instance: MyVanna, 
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
            await progress_callback(35, "Loading training data...")
        
        try:
            with open(training_data_path, 'r') as f:
                training_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load training data: {e}")
        
        documentation = training_data.get('documentation', [])
        examples = training_data.get('examples', [])
        
        logger.info(f"Training Vanna with {len(documentation)} docs and {len(examples)} examples for connection {connection_id}{user_info}")
        
        total_items = len(documentation) + len(examples)
        current_item = 0
        
        if progress_callback:
            await progress_callback(40, f"Training with {len(documentation)} documentation entries...")
        
        # Train with documentation
        for doc_entry in documentation:
            content = doc_entry.get('content')
            if content:
                try:
                    vanna_instance.train(documentation=content)
                    current_item += 1
                    progress = 40 + int((current_item / total_items) * 40)
                    if progress_callback:
                        await progress_callback(progress, f"Training documentation: {doc_entry.get('doc_type', 'unknown')}")
                except Exception as e:
                    logger.error(f"Failed to train documentation entry: {e}")
                    current_item += 1
                    continue
        
        if progress_callback:
            await progress_callback(80, f"Training with {len(examples)} examples...")
        
        # Train with examples
        for example_entry in examples:
            question = example_entry.get('question')
            sql = example_entry.get('sql')
            if question and sql:
                try:
                    vanna_instance.train(question=question, sql=sql)
                    current_item += 1
                    progress = 40 + int((current_item / total_items) * 40)
                    if progress_callback:
                        await progress_callback(progress, f"Training example: {question[:50]}...")
                except Exception as e:
                    logger.error(f"Failed to train example: {e}")
                    current_item += 1
                    continue
        
        if progress_callback:
            await progress_callback(95, "Training completed, saving model...")
        
        logger.info(f"Vanna training completed for connection {connection_id}{user_info}")
    
    def create_vanna_instance(
        self, 
        connection_id: str, 
        db_config: DatabaseConfig, 
        vanna_config: VannaConfig,
        user: Optional[User] = None
    ) -> Optional[MyVanna]:
        """Create a fresh Vanna instance for querying - STATELESS"""
        
        user_info = f" for user {user.email}" if user else ""
        
        try:
            # Check if trained model exists - use latest directory
            chromadb_path = self._get_latest_chromadb_path(connection_id)
            
            if not chromadb_path or not os.path.exists(chromadb_path):
                logger.warning(f"No trained model found for connection {connection_id}{user_info}")
                return None
            
            # Create fresh instance - NO CACHING
            vanna_instance = MyVanna(config={
                "api_key": vanna_config.api_key,
                "base_url": vanna_config.base_url,
                "model": vanna_config.model,
                "path": chromadb_path
            })
            
            # Connect to database
            odbc_conn_str = db_config.to_odbc_connection_string()
            vanna_instance.connect_to_mssql(odbc_conn_str=odbc_conn_str)
            
            logger.info(f"Fresh Vanna instance created for connection {connection_id}{user_info}")
            return vanna_instance
            
        except Exception as e:
            logger.error(f"Failed to create Vanna instance for connection {connection_id}{user_info}: {e}")
            return None
    
    def cleanup_connection_model(self, connection_id: str, user: Optional[User] = None) -> bool:
        """Clean up Vanna model files for a connection"""
        user_info = f" for user {user.email}" if user else ""
        
        try:
            # Force cleanup ChromaDB
            self._force_cleanup_chromadb(connection_id)
            
            # Clean up training data
            training_data_path = os.path.join(self.data_dir, "connections", connection_id, "generated_training_data.json")
            if os.path.exists(training_data_path):
                os.remove(training_data_path)
                logger.info(f"Cleaned up training data for connection {connection_id}{user_info}")
            
            # Force garbage collection
            gc.collect()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup Vanna model for connection {connection_id}{user_info}: {e}")
            return False


# Global vanna service instance
vanna_service = VannaService()