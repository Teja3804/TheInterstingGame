"""
Main Orchestrator - Runs all necessary scripts and activates all components
Execute this single file to run the entire system
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text):
    """Print success message."""
    try:
        print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[OK] {text}")

def print_error(text):
    """Print error message."""
    try:
        print(f"{Colors.RED}[ERROR] {text}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[ERROR] {text}")

def print_info(text):
    """Print info message."""
    try:
        print(f"{Colors.YELLOW}[INFO] {text}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[INFO] {text}")

def run_python_script(script_name, description):
    """Run a Python script and handle errors."""
    print(f"\n{Colors.BOLD}Running: {description}{Colors.RESET}")
    print(f"Script: {script_name}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        print_success(f"{description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print_error(f"Script not found: {script_name}")
        return False

def check_file_exists(filepath, description):
    """Check if a file exists."""
    if os.path.exists(filepath):
        print_success(f"{description} exists: {filepath}")
        return True
    else:
        print_error(f"{description} not found: {filepath}")
        return False

def check_node_installed():
    """Check if Node.js is installed."""
    try:
        result = subprocess.run(
            ['node', '--version'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_success(f"Node.js is installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print_info("Node.js not found - React frontend will be skipped")
    return False

def install_npm_dependencies():
    """Install npm dependencies for frontend."""
    frontend_dir = Path('frontend')
    if not frontend_dir.exists():
        print_info("Frontend directory not found - skipping npm install")
        return False
    
    print(f"\n{Colors.BOLD}Installing npm dependencies...{Colors.RESET}")
    os.chdir('frontend')
    
    try:
        result = subprocess.run(
            ['npm', 'install'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        os.chdir('..')
        
        if result.returncode == 0:
            print_success("npm dependencies installed successfully")
            return True
        else:
            print_error("npm install failed")
            if result.stderr:
                print(result.stderr)
            os.chdir('..')
            return False
    except FileNotFoundError:
        print_error("npm not found - please install Node.js")
        os.chdir('..')
        return False

def start_frontend_server():
    """Start the frontend development server."""
    frontend_dir = Path('frontend')
    if not frontend_dir.exists():
        print_info("Frontend directory not found - skipping frontend server")
        return None
    
    if not check_node_installed():
        return None
    
    print(f"\n{Colors.BOLD}Starting frontend development server...{Colors.RESET}")
    print_info("The server will run in the background")
    print_info("Press Ctrl+C to stop the server when done")
    
    os.chdir('frontend')
    
    try:
        # Start npm run dev in background
        process = subprocess.Popen(
            ['npm', 'run', 'dev'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        os.chdir('..')
        
        print_success("Frontend server started")
        print_info("Check the terminal output for the server URL (usually http://localhost:5173)")
        return process
    except FileNotFoundError:
        print_error("npm not found")
        os.chdir('..')
        return None

def main():
    """Main orchestrator function."""
    print_header("The Interest Game - Main Orchestrator")
    print("This script will:")
    print("  1. Generate chart data (generate_data.py)")
    print("  2. Generate HTML chart (generate_chart.py)")
    print("  3. Install npm dependencies (if needed)")
    print("  4. Start frontend server (optional)")
    
    # Get current directory
    base_dir = Path.cwd()
    print(f"\nWorking directory: {base_dir}")
    
    # Step 1: Generate data for React frontend
    print_header("Step 1: Generating React Frontend Data")
    if not run_python_script('generate_data.py', 'Generate React frontend data'):
        print_error("Failed to generate frontend data")
        return False
    
    # Verify data file was created
    data_file = base_dir / 'frontend' / 'public' / 'data.json'
    if not check_file_exists(data_file, 'Frontend data file'):
        print_error("Data file was not created - frontend may not work")
    
    # Step 2: Generate HTML chart
    print_header("Step 2: Generating HTML Chart")
    if not run_python_script('generate_chart.py', 'Generate HTML chart'):
        print_error("Failed to generate HTML chart")
        return False
    
    # Verify HTML file was created
    html_file = base_dir / 'candlestick_chart.html'
    if not check_file_exists(html_file, 'HTML chart file'):
        print_error("HTML chart was not created")
    
    # Step 3: Check npm dependencies
    print_header("Step 3: Checking Frontend Dependencies")
    frontend_dir = base_dir / 'frontend'
    node_modules = frontend_dir / 'node_modules'
    
    if frontend_dir.exists():
        if not node_modules.exists():
            print_info("node_modules not found - installing dependencies...")
            if not install_npm_dependencies():
                print_info("npm install failed - you can manually run: cd frontend && npm install")
        else:
            print_success("npm dependencies already installed")
    else:
        print_info("Frontend directory not found - skipping frontend setup")
    
    # Step 4: Summary and next steps
    print_header("Summary")
    print_success("All scripts executed successfully!")
    print("\nGenerated files:")
    if html_file.exists():
        print(f"  • {html_file} - Open this file in your browser")
    if data_file.exists():
        print(f"  • {data_file} - React frontend data")
    
    print("\nNext steps:")
    print("  1. Open 'candlestick_chart.html' in your browser to view the chart")
    
    if frontend_dir.exists() and node_modules.exists():
        print("\n  2. For React frontend:")
        print("     Option A: Run manually:")
        print("       cd frontend")
        print("       npm run dev")
        print("\n     Option B: Start automatically now? (y/n): ", end='')
        
        try:
            response = input().strip().lower()
            if response == 'y' or response == 'yes':
                process = start_frontend_server()
                if process:
                    print("\n" + "="*60)
                    print("Frontend server is running!")
                    print("Press Ctrl+C to stop this script and the server")
                    print("="*60)
                    try:
                        process.wait()
                    except KeyboardInterrupt:
                        print("\n\nStopping server...")
                        process.terminate()
                        process.wait()
                        print_success("Server stopped")
        except KeyboardInterrupt:
            print("\n\nSkipping frontend server startup")
    
    print("\n" + "="*60)
    print_success("All done! Happy trading! 📈")
    print("="*60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n" + Colors.YELLOW + "Interrupted by user" + Colors.RESET)
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

