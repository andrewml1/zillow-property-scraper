import csv
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console

console = Console()

class DataStorage:
    """
    Handles the storage and retrieval of property data in various formats.
    """
    def __init__(self, data_dir: str = "data_exports"):
        """
        Initialize storage with a directory for exports.
        Args:
            data_dir: Directory to store data exports (default: "data_exports")
        """
        self.data_dir = data_dir
        # Create the directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
    
    def _generate_filename(self, location: str, extension: str) -> str:
        """Generate a filename based on location and timestamp."""
        # Clean location for filename (remove special chars)
        clean_location = ''.join(c if c.isalnum() else '_' for c in location)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{clean_location}_{timestamp}.{extension}"
    
    def export_to_csv(self, properties: List[Dict[str, Any]], location: str) -> str:
        """
        Export property data to CSV file.
        
        Args:
            properties: List of property dictionaries
            location: Location name used in the search
            
        Returns:
            Path to the saved CSV file
        """
        if not properties:
            console.print("[yellow]No properties to export.[/yellow]")
            return ""
        
        filename = self._generate_filename(location, "csv")
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                # Get fieldnames from the first property
                fieldnames = properties[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for prop in properties:
                    writer.writerow(prop)
            
            console.print(f"[green]✓ Exported {len(properties)} properties to [bold]{filepath}[/bold][/green]")
            return filepath
        
        except Exception as e:
            console.print(f"[red]Error exporting to CSV: {str(e)}[/red]")
            return ""
    
    def export_to_json(self, properties: List[Dict[str, Any]], location: str) -> str:
        """
        Export property data to JSON file.
        
        Args:
            properties: List of property dictionaries
            location: Location name used in the search
            
        Returns:
            Path to the saved JSON file
        """
        if not properties:
            console.print("[yellow]No properties to export.[/yellow]")
            return ""
        
        filename = self._generate_filename(location, "json")
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump({
                    "location": location,
                    "timestamp": datetime.now().isoformat(),
                    "properties": properties
                }, jsonfile, indent=2)
            
            console.print(f"[green]✓ Exported {len(properties)} properties to [bold]{filepath}[/bold][/green]")
            return filepath
        
        except Exception as e:
            console.print(f"[red]Error exporting to JSON: {str(e)}[/red]")
            return ""
