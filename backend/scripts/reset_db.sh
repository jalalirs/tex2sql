#!/bin/bash

# Database Reset Script
# This script stops the database, removes volumes, and recreates everything

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
POSTGRES_CONTAINER="tex2sql_postgres"
DATABASE_NAME="tex2sql"
POSTGRES_USER="postgres"

# Function to print colored messages
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if compose file exists
check_compose_file() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "Docker compose file '$COMPOSE_FILE' not found in current directory."
        print_message "Please run this script from your project root directory."
        exit 1
    fi
}

# Function to backup existing data (optional)
backup_data() {
    if [ "$1" = "--backup" ]; then
        print_message "Creating backup of existing data..."
        BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Check if container is running
        if docker ps --format "table {{.Names}}" | grep -q "$POSTGRES_CONTAINER"; then
            print_message "Backing up database to $BACKUP_DIR/database_backup.sql"
            docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" "$DATABASE_NAME" > "$BACKUP_DIR/database_backup.sql"
            print_success "Database backup created at $BACKUP_DIR/database_backup.sql"
        else
            print_warning "Container not running, skipping database backup"
        fi
    fi
}

# Function to stop containers
stop_containers() {
    print_message "Stopping all containers..."
    if docker compose down; then
        print_success "Containers stopped successfully"
    else
        print_error "Failed to stop containers"
        exit 1
    fi
}

# Function to remove volumes
remove_volumes() {
    print_message "Removing PostgreSQL volumes..."
    
    # Get all volumes related to this project
    PROJECT_NAME=$(basename "$PWD")
    VOLUMES=$(docker volume ls --filter name="${PROJECT_NAME}" --format "{{.Name}}" | grep postgres || true)
    
    if [ -z "$VOLUMES" ]; then
        print_warning "No PostgreSQL volumes found for project '$PROJECT_NAME'"
        # Try common volume names
        COMMON_VOLUMES="postgres_data ${PROJECT_NAME}_postgres_data"
        for vol in $COMMON_VOLUMES; do
            if docker volume ls | grep -q "$vol"; then
                print_message "Found volume: $vol"
                docker volume rm "$vol" || print_warning "Could not remove volume $vol"
            fi
        done
    else
        for volume in $VOLUMES; do
            print_message "Removing volume: $volume"
            if docker volume rm "$volume"; then
                print_success "Volume $volume removed"
            else
                print_warning "Could not remove volume $volume (might not exist)"
            fi
        done
    fi
}

# Function to remove orphaned volumes
remove_orphaned_volumes() {
    print_message "Removing orphaned volumes..."
    docker volume prune -f
    print_success "Orphaned volumes removed"
}

# Function to start containers
start_containers() {
    print_message "Starting containers..."
    if docker compose up -d; then
        print_success "Containers started successfully"
    else
        print_error "Failed to start containers"
        exit 1
    fi
}

# Function to wait for database to be ready
wait_for_database() {
    print_message "Waiting for database to be ready..."
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
            print_success "Database is ready!"
            return 0
        fi
        
        print_message "Attempt $attempt/$max_attempts - waiting for database..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "Database failed to start after $max_attempts attempts"
    exit 1
}

# Function to initialize Alembic if needed
initialize_alembic() {
    if [ ! -d "alembic" ] || [ ! -f "alembic.ini" ]; then
        print_message "Alembic not initialized. Initializing now..."
        if alembic init alembic; then
            print_success "Alembic initialized successfully"
            print_warning "Please update alembic/env.py to import your models before running migrations"
            print_message "Add this line to alembic/env.py: from app.models import Base"
            print_message "And set: target_metadata = Base.metadata"
            return 1  # Return 1 to indicate manual setup needed
        else
            print_error "Failed to initialize Alembic"
            exit 1
        fi
    fi
    return 0  # Already initialized
}

# Function to create initial migration if none exist
create_initial_migration() {
    # Check if any migrations exist
    if [ ! -d "alembic/versions" ] || [ -z "$(ls -A alembic/versions/ 2>/dev/null)" ]; then
        print_message "No migrations found. Creating initial migration..."
        if alembic revision --autogenerate -m "Initial migration with connections table"; then
            print_success "Initial migration created successfully"
        else
            print_error "Failed to create initial migration"
            print_message "Make sure your models are properly imported in alembic/env.py"
            exit 1
        fi
    else
        print_message "Existing migrations found"
    fi
}

# Function to run Alembic migrations
run_alembic_migrations() {
    print_message "Setting up Alembic and running migrations..."
    
    # Check if alembic is available
    if ! command -v alembic &> /dev/null; then
        print_error "Alembic not found. Please install it: pip install alembic"
        exit 1
    fi
    
    # Initialize if needed
    if ! initialize_alembic; then
        print_warning "Alembic was just initialized. Please:"
        print_message "1. Update alembic/env.py to import your models"
        print_message "2. Run: alembic revision --autogenerate -m 'Initial migration'"
        print_message "3. Run this script again"
        exit 0
    fi
    
    # Create initial migration if needed
    create_initial_migration
    
    # Run migrations
    print_message "Applying migrations..."
    if alembic upgrade head; then
        print_success "Alembic migrations completed successfully"
    else
        print_error "Alembic migrations failed"
        exit 1
    fi
}

# Function to verify database setup
verify_database() {
    print_message "Verifying database setup..."
    
    # Check if connections table exists and has driver column
    if docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$DATABASE_NAME" -c "\d connections" > /dev/null 2>&1; then
        print_success "Connections table exists"
        
        # Check for driver column
        if docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$DATABASE_NAME" -c "\d connections" | grep -q "driver"; then
            print_success "Driver column found in connections table"
        else
            print_warning "Driver column not found in connections table"
        fi
    else
        print_warning "Connections table not found"
        print_message "This is expected if using Alembic - tables will be created by migrations"
    fi
}

# Function to show database info
show_database_info() {
    print_message "Database connection information:"
    echo "  Host: localhost"
    echo "  Port: 5432"
    echo "  Database: $DATABASE_NAME"
    echo "  Username: $POSTGRES_USER"
    echo "  Password: password123"
    echo ""
    print_message "To connect manually:"
    echo "  docker exec -it $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $DATABASE_NAME"
}

# Function to show help
show_help() {
    echo "Database Reset Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --backup          Create a backup before resetting"
    echo "  --force           Skip confirmation prompt"
    echo "  --no-migrations   Skip running Alembic migrations"
    echo "  --help            Show this help message"
    echo ""
    echo "This script will:"
    echo "  1. Stop all Docker containers"
    echo "  2. Remove PostgreSQL volumes (all data will be lost)"
    echo "  3. Start containers again (recreates empty database)"
    echo "  4. Run Alembic migrations to create schema"
    echo "  5. Verify the database is working"
    echo ""
}

# Main function
main() {
    echo "========================================"
    echo "     Database Reset Script"
    echo "========================================"
    echo ""
    
    # Parse arguments
    BACKUP=false
    FORCE=false
    NO_MIGRATIONS=false
    
    for arg in "$@"; do
        case $arg in
            --backup)
                BACKUP=true
                ;;
            --force)
                FORCE=true
                ;;
            --no-migrations)
                NO_MIGRATIONS=true
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $arg"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Pre-flight checks
    check_docker
    check_compose_file
    
    # Warning message
    print_warning "This will COMPLETELY RESET your database!"
    print_warning "ALL DATA WILL BE LOST!"
    echo ""
    
    if [ "$FORCE" = false ]; then
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_message "Operation cancelled."
            exit 0
        fi
    fi
    
    echo ""
    print_message "Starting database reset process..."
    echo ""
    
    # Execute reset steps
    if [ "$BACKUP" = true ]; then
        backup_data --backup
        echo ""
    fi
    
    stop_containers
    echo ""
    
    remove_volumes
    echo ""
    
    start_containers
    echo ""
    
    wait_for_database
    echo ""
    
    if [ "$NO_MIGRATIONS" = false ]; then
        run_alembic_migrations
        echo ""
    else
        print_warning "Skipping Alembic migrations (--no-migrations flag used)"
        echo ""
    fi
    
    verify_database
    echo ""
    
    show_database_info
    echo ""
    
    print_success "Database reset completed successfully!"
    print_message "Your database is now ready with a fresh schema including the driver column."
}

# Run main function with all arguments
main "$@"