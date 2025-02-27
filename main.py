import asyncio
from ui.cli import ZillowCLI

async def main():
    cli = ZillowCLI()
    await cli.run()

if __name__ == "__main__":
    asyncio.run(main())
