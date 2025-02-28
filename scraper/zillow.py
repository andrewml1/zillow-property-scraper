import asyncio
import re
import time
import random
from DrissionPage import ChromiumPage, ChromiumOptions
from rich.console import Console
from bs4 import BeautifulSoup

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
    """Formats a location string into a Zillow-friendly URL format"""
    location = location.strip().lower()
    location = re.sub(r'\s+', '-', location)
    location = re.sub(r'[^\w\s-]', '', location)
    return f"https://www.zillow.com/homes/{location}_rb/"

async def validate_location_search(search_query: str) -> tuple[bool, str, str]:
    """Validates and formats a location search query"""
    cleaned_query = re.sub(r'\s+', ' ', search_query.strip())

    if not cleaned_query:
        return False, "", "Search query cannot be empty"

    location_parts = [part.strip() for part in cleaned_query.split(',')]

    if len(location_parts) != 2:
        return False, "", "Please enter both city and state (e.g., 'Los Angeles, California')"

    city = ' '.join(word.capitalize() for word in location_parts[0].split())
    state = location_parts[1].strip().upper()

    if len(state) > 2:
        state = STATE_MAPPING.get(state)
        if not state:
            return False, "", "Invalid state name. Please enter a valid US state"
    elif len(state) != 2:
        return False, "", "Invalid state format. Please enter full state name or two-letter code"

    formatted_location = f"{city}, {state}"
    zillow_url = format_zillow_url(formatted_location)

    return True, formatted_location, zillow_url

async def scrape_zillow_data(zillow_url: str, max_pages: int = 2):
    """Scrapes Zillow property data with anti-detection measures"""
    co = ChromiumOptions()
    co.headless(True)
    page = ChromiumPage(co)
    properties_data = []
    total_properties = 0
    current_page = 1
    scrape_all_pages = (max_pages == -1)
    previous_page_last_property_id = None  # Store the last property ID of the previous page
    should_continue_scraping = True

    try:
        console.print("\n[bold blue]Starting Zillow Property Scraper[/bold blue]")
        console.print("[dim]Press Ctrl+C to stop at any time[/dim]\n")

        page.set.user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
        page.set.timeouts(30, 30, 30)
        page.set.scroll.smooth(True)
        page.set.scroll.wait_complete(True)

        while should_continue_scraping and (scrape_all_pages or current_page <= max_pages):
            console.print(f"[yellow]━━ Scraping page {current_page} of {'all' if scrape_all_pages else max_pages} ━━[/yellow]")

            if current_page == 1:
                console.print("[cyan]Loading initial page...[/cyan]")
                await asyncio.sleep(2 + random.random() * 2)
                page.get(zillow_url, timeout=30)
                console.print("[cyan]First page loaded. Processing property data...[/cyan]")
                await asyncio.sleep(3 + random.random() * 3)
            else:
                console.print("[cyan]Waiting before loading next page (anti-bot measures)...[/cyan]")
                wait_time = 1 + random.random() * 1
                console.print(f"[dim]Waiting {wait_time:.1f} seconds...[/dim]")
                await asyncio.sleep(wait_time)

            try:
                page.wait.doc_loaded(timeout=15)
                wait_after_load = 1 + random.random() * (2 if current_page > 1 else 1)
                await asyncio.sleep(wait_after_load)
            except:
                pass

            try:
                page.wait.ele_displayed('css:[data-test="property-card"]', timeout=15)
            except:
                if current_page > 1:
                    console.print("[yellow]Page elements not found. Potential network issue - reloading page...[/yellow]")
                    page.refresh()
                    await asyncio.sleep(3 + random.random() * 2)
                    try:
                        page.wait.ele_displayed('css:[data-test="property-card"]', timeout=15)
                    except:
                        break
                else:
                    break

            page_properties = set()
            properties_found_this_page = 0
            last_count = 0

            while True:  # Inner loop to process property cards on the current page
                property_cards = page.eles('css:[data-test="property-card"]')
                current_count = len(property_cards)

                for card in property_cards[last_count:]:
                    try:
                        price_element = card.ele('css:[data-test="property-card-price"]')
                        address_element = card.ele('css:address[data-test="property-card-addr"]')

                        if not price_element or not address_element:
                            continue

                        price = price_element.text.strip()
                        address = address_element.text.strip()

                        property_id = f"{address}|{price}"
                        if property_id in page_properties:
                            continue

                        page_properties.add(property_id)

                        beds = "N/A"
                        baths = "N/A"
                        sqft = "N/A"
                        property_type = "N/A"

                        try:
                            details_list = card.ele('css:ul.StyledPropertyCardHomeDetailsList-c11n-8-109-3__sc-1j0som5-0')
                            if details_list:
                                list_items = details_list.eles('tag:li')
                                if len(list_items) >= 1:
                                    beds = list_items[0].text.replace('bds', '').strip()
                                    if beds != "Studio" and "bd" in beds:
                                        beds = beds.replace('bd', '').strip()
                                if len(list_items) >= 2:
                                    baths = list_items[1].text.replace('ba', '').strip()
                                if len(list_items) >= 3:
                                    sqft = list_items[2].text.replace('sqft', '').strip()

                            card = page.ele("css:div.StyledPropertyCardDataArea-c11n-8-109-3__sc-10i1r6-0")
                            property_texts = card.texts()  # Obtener todos los textos dentro del elemento como lista
                            property_text = " ".join(property_texts)  # Convertir lista en una sola cadena de texto
                            property_type = property_text.split("-")[-1].strip()  # Extraer el tipo de propiedad

                        except Exception as e:
                            pass

                        # Replace any "--" values with "N/A" for consistency
                        beds = "N/A" if beds == "--" else beds
                        baths = "N/A" if baths == "--" else baths
                        sqft = "N/A" if sqft == "--" else sqft
                        property_type = "N/A" if property_type == "--" else property_type

                        properties_data.append({
                            'address': address,
                            'price': price,
                            'beds': beds,
                            'baths': baths,
                            'sqft': sqft,
                            'property_type': property_type
                        })
                        properties_found_this_page += 1
                    except Exception as e:
                        continue

                last_count = current_count

                # Check for pagination element visibility
                try:
                    pagination = page.ele('css:.search-pagination')
                    if pagination and pagination.is_displayed():
                        break  # Stop scrolling if pagination appears
                except:
                    pass #in case if it doesnt find it

                # Gradual scrolling logic (simplified)
                scroll_increment = 1000 + random.randint(0, 100)  # Dynamic scroll height
                page.scroll.down(scroll_increment)
                await asyncio.sleep(0.7 + random.random() * 0.8)  # Wait between scrolls

                if len(page.eles('css:[data-test="property-card"]')) == current_count:
                        break

            # --- Check for Repetition BEFORE adding to total and BEFORE pagination ---
            if properties_found_this_page > 0:
                current_page_last_property_id = f"{properties_data[-1]['address']}|{properties_data[-1]['price']}"
                if current_page_last_property_id == previous_page_last_property_id:
                    console.print("[yellow]Detected repetition of last page. Stopping.[/yellow]")
                    should_continue_scraping = False  # Stop the outer loop
                    total_properties += properties_found_this_page  # Add the properties from the LAST page
                    console.print(f"[green]✓ Page {current_page}: Successfully scraped {properties_found_this_page} properties[/green]")
                    console.print("─" * 50 + "\n")
                    break  # VERY IMPORTANT: Break the OUTER loop here!

                previous_page_last_property_id = current_page_last_property_id

            # Only add to total and print if we haven't detected a repetition
            if should_continue_scraping:
                total_properties += properties_found_this_page
                console.print(f"[green]✓ Page {current_page}: Successfully scraped {properties_found_this_page} properties[/green]")
                console.print("─" * 50 + "\n")

            if scrape_all_pages or current_page < max_pages:
                try:
                    next_button = page.ele('css:a[rel="next"]')
                    if not next_button:
                        next_button = page.ele('css:a[title="Next page"]')
                        if not next_button:
                            next_button = page.ele('css:.search-pagination a:last-child')

                    if not next_button:
                        if scrape_all_pages:
                            break
                        else:
                            break

                    # Check if the next button is disabled
                    if next_button.attr('aria-disabled') == 'true':
                        console.print("[yellow]Next button disabled.  End of pagination.[/yellow]")
                        break

                    current_url = page.url
                    next_button.click()
                    page.wait.url_change(current_url, timeout=15)
                    current_page += 1
                except Exception as e:
                    break  # No more pages, or error clicking next.
            else:
                break

        console.print("\n[bold green]━━━ Scraping Complete! ━━━[/bold green]")
        console.print(f"[bold]Total Pages Scraped: [cyan]{current_page}[/cyan][/bold]")
        console.print(f"[bold]Total Properties Found: [cyan]{total_properties}[/cyan][/bold]\n")

        return properties_data

    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        return []
    finally:
        page.quit()
