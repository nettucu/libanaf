from rich.console import Console
from rich.table import Table

# Create a console object to render the output
console = Console()

# --- Create the INNER table for a specific employee's projects ---
project_table = Table(title="Current Projects", show_header=True, header_style="bold magenta")
project_table.add_column("Project Name", style="cyan")
project_table.add_column("Status", style="green")

project_table.add_row("Project Alpha", "In Progress")
project_table.add_row("Project Beta", "Completed")

# --- Create the OUTER table for the employee list ---
employee_table = Table(title="Employee Overview", show_header=True, header_style="bold blue")
employee_table.add_column("ID", style="dim", width=6)
employee_table.add_column("Employee Name")
employee_table.add_column("Details")  # This column will hold our nested table

# --- Add rows to the outer table ---
# Add a simple row for an employee with no complex details
employee_table.add_row("101", "Alice", "On vacation")

# Add a row where the 'Details' cell is the entire inner table
employee_table.add_row("102", "Bob", project_table)

# Render the final, nested table to the console
console.print(employee_table)
