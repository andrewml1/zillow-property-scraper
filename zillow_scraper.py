import asyncio
import re
import time
from DrissionPage import ChromiumPage
from rich.console import Console
from rich.prompt import Prompt

console = Console()

STATE_MAPPING = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR', 'CALIFORNIA': 'CA',
    'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE', 'FLORIDA': 'FL', 'GEORGIA': 'GA',
    'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA',
    'KANSAS': 'KS', 'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO',
    'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
    'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH',
    'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
    'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT',
    'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY'
}

def format_zillow_url(location: str) -> str:
    """
    Formats a location string into a Zillow-friendly URL format
    Example: "Los Angeles, CA" -> "https://www.zillow.com/homes/los-angeles-ca_rb/"
    """
    # Remove any extra whitespace and convert to lowercase
    location = location.strip().lower()
    # Replace spaces with hyphens
    location = re.sub(r'\s+', '-', location)
    # Remove any special characters
    location = re.sub(r'[^\w\s-]', '', location)
    # Create the full Zillow URL
    return f"https://www.zillow.com/homes/{location}_rb/"

async def validate_location_search(search_query: str) -> tuple[bool, str, str]:
    """
    Validates and formats a location search query locally.
    Returns (is_valid, formatted_query, zillow_url)
    """
    # Clean and format the input
    cleaned_query = re.sub(r'\s+', ' ', search_query.strip())

    if not cleaned_query:
        return False, "", "Search query cannot be empty"

    # Split into city and state parts
    location_parts = [part.strip() for part in cleaned_query.split(',')]

    if len(location_parts) != 2:
        return False, "", "Please enter both city and state (e.g., 'Los Angeles, California')"

    # Get city name and capitalize each word
    city = ' '.join(word.capitalize() for word in location_parts[0].split())

    # Handle state conversion
    state = location_parts[1].strip().upper()
    if len(state) > 2:  # If full state name provided
        state = STATE_MAPPING.get(state)
        if not state:
            return False, "", "Invalid state name. Please enter a valid US state"
    elif len(state) != 2:
        return False, "", "Invalid state format. Please enter full state name or two-letter code"

    formatted_location = f"{city}, {state}"
    zillow_url = format_zillow_url(formatted_location)

    return True, formatted_location, zillow_url

async def get_search_location() -> tuple[str, str]:
    """
    Interactive CLI function to get and validate search location
    Returns (formatted_location, zillow_url)
    """
    while True:
        search_query = Prompt.ask(
            "[bold blue]Enter location to search[/bold blue]\n"
            "[dim]Format: 'Location, State' (e.g., 'New Tampa, Florida' or 'Brooklyn, NY')\n"
            "Location can be a city, neighborhood, or area[/dim]"
        )

        console.print("[yellow]Validating location format...[/yellow]")
        is_valid, formatted_location, zillow_url = await validate_location_search(search_query)

        if is_valid:
            console.print(f"[green]Using location: {formatted_location}[/green]")
            console.print(f"[dim]Zillow search URL: {zillow_url}[/dim]")
            return formatted_location, zillow_url
        else:
            console.print(f"[red]{formatted_location}[/red]")  # formatted_location contains error message in this case
            suggestion = Prompt.ask(
                "[yellow]Would you like to try another search?[/yellow]",
                choices=["yes", "no"],
                default="yes"
            )
            if suggestion.lower() != "yes":
                raise ValueError("Search cancelled by user")

async def scrape_zillow_data(zillow_url: str, max_pages: int = 2):
    """
    Scrapes Zillow for property price and address using DrissionPage.
    max_pages: Maximum number of pages to scrape (default: 2)
    """
    page = ChromiumPage()
    properties_data = []
    total_properties = 0
    current_page = 1

    try:
        console.print("\n[bold blue]Starting Zillow Property Scraper[/bold blue]")
        console.print("[dim]Press Ctrl+C to stop at any time[/dim]\n")

        while current_page <= max_pages:
            console.print(f"[yellow]━━ Scraping page {current_page} of {max_pages} ━━[/yellow]")
            
            # Get the page
            page.get(zillow_url, timeout=30)
            page.wait.doc_loaded()

            # Disable smooth scrolling for better stability
            page.set.scroll.smooth(False)
            page.set.scroll.wait_complete(True)

            # Wait for the property cards container
            try:
                page.wait.ele_displayed('css:[data-testid="search-page-list-container"]', timeout=10)
            except:
                console.print("[yellow]No property container found.[/yellow]")
                break

            # Initialize tracking variables
            page_properties = set()
            last_count = 0
            scroll_height = 600
            total_scrolled = 0
            properties_found_this_page = 0
            
            while True:
                # Process current visible properties
                property_cards = page.eles('css:[data-test="property-card"]')
                current_count = len(property_cards)
                
                # Process only new cards since last scroll
                for card in property_cards[last_count:]:
                    try:
                        price_element = card.ele('css:[data-test="property-card-price"]')
                        address_element = card.ele('css:address[data-test="property-card-addr"]')

                        price = price_element.text if price_element else "N/A"
                        address = address_element.text if address_element else "N/A"

                        property_key = f"{address}_{price}"
                        if property_key not in page_properties:
                            page_properties.add(property_key)
                            properties_data.append({'address': address, 'price': price})
                            properties_found_this_page += 1
                    except:
                        continue

                # Update last count for next iteration
                last_count = current_count

                # Show progress update every 10 properties
                if properties_found_this_page > 0 and properties_found_this_page % 10 == 0:
                    console.print(f"[dim]⌛ Processing... Found {properties_found_this_page} properties[/dim]")

                # Check if pagination is visible
                try:
                    pagination = page.ele('css:.search-pagination')
                    if pagination and pagination.is_displayed():
                        console.print("[dim]Reached pagination, moving to next page...[/dim]")
                        break
                except:
                    pass

                # Scroll gradually with smaller increments
                page.scroll.down(scroll_height)
                total_scrolled += scroll_height
                
                # Wait longer between scrolls
                page.wait(2)

                # If no new properties after scroll, try one more time
                if len(page.eles('css:[data-test="property-card"]')) == current_count:
                    page.wait(2)  # Wait a bit more
                    if len(page.eles('css:[data-test="property-card"]')) == current_count:
                        # Try one final small scroll
                        page.scroll.down(100)
                        page.wait(2)
                        if len(page.eles('css:[data-test="property-card"]')) == current_count:
                            console.print("[yellow]No new properties found after scroll.[/yellow]")
                            break

            total_properties += properties_found_this_page
            console.print(f"[green]✓ Page {current_page}: Successfully scraped {properties_found_this_page} properties[/green]")
            console.print("─" * 50 + "\n")

            # If we haven't reached max_pages, try to go to next page
            if current_page < max_pages:
                try:
                    next_button = page.ele('css:a[rel="next"]')
                    if not next_button:
                        console.print("[yellow]No next page button found.[/yellow]")
                        break
                    
                    current_url = page.url
                    next_button.click()
                    page.wait.url_change(current_url, timeout=10)
                    page.wait(2)
                    current_page += 1
                except Exception as e:
                    console.print(f"[red]Error navigating to next page: {str(e)}[/red]")
                    break
            else:
                break

        # Final results display
        console.print("\n[bold green]━━━ Scraping Complete! ━━━[/bold green]")
        console.print(f"[bold]Total Pages Scraped: [cyan]{current_page}[/cyan][/bold]")
        console.print(f"[bold]Total Properties Found: [cyan]{total_properties}[/cyan][/bold]\n")
        
        if properties_data:
            console.print("[bold]━━━ Property Listings ━━━[/bold]")
            for i, prop in enumerate(properties_data, 1):
                console.print(f"[bold cyan]{i:2d}.[/bold cyan] [yellow]{prop['address']}[/yellow]")
                console.print(f"    [green]Price: {prop['price']}[/green]")
        else:
            console.print("[red]No properties were found.[/red]")

        return properties_data

    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        return []
    finally:
        page.quit()

async def main():
    try:
        location, zillow_url = await get_search_location()
        await scrape_zillow_data(zillow_url)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main())
