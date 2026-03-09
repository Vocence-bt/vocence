"""
Logging utilities for Vocence validator.

Provides formatted, timestamped log messages with color-coded prefixes.
"""

from datetime import datetime

from rich import print as rprint


def print_banner() -> None:
    """Print the Vocence ASCII art banner (e.g. on CLI start). Uses Rich for bold cyan/white."""
    rprint("""
[bold cyan]
██╗   ██╗ ██████╗  ██████╗███████╗███╗   ██╗ ██████╗███████╗
██║   ██║██╔═══██╗██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
██║   ██║██║   ██║██║     █████╗  ██╔██╗ ██║██║     █████╗
╚██╗ ██╔╝██║   ██║██║     ██╔══╝  ██║╚██╗██║██║     ██╔══╝
 ╚████╔╝ ╚██████╔╝╚██████╗███████╗██║ ╚████║╚██████╗███████╗
  ╚═══╝   ╚═════╝  ╚═════╝╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝
[/bold cyan]

[bold white]real-time ai voice engine[/bold white]
""")


def emit_log(message: str, severity: str = "info") -> None:
    """Format and print timestamped log messages with color-coded prefixes.
    
    Args:
        message: The message to log
        severity: Log severity - one of "info", "success", "error", "warn", "start"
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    severity_prefixes = {
        "info": f"\033[90m{timestamp}\033[0m \033[36m▸\033[0m",
        "success": f"\033[90m{timestamp}\033[0m \033[32m✓\033[0m",
        "error": f"\033[90m{timestamp}\033[0m \033[31m✗\033[0m",
        "warn": f"\033[90m{timestamp}\033[0m \033[33m⚠\033[0m",
        "start": f"\033[90m{timestamp}\033[0m \033[33m→\033[0m",
    }
    print(f"{severity_prefixes.get(severity, f'\033[90m{timestamp}\033[0m  ')} {message}")


def print_header(header_text: str) -> None:
    """Print a bold section header.
    
    Args:
        header_text: The header text to display
    """
    print(f"\n\033[1m{'─' * 60}\033[0m\n\033[1m{header_text}\033[0m\n\033[1m{'─' * 60}\033[0m\n")

