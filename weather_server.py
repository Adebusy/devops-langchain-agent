from mcp.server.fastmcp import FastMCP
import asyncio
# from langchain_openai import llms

mcp = FastMCP("weather")

# llms = llms.OpenAI(model="gpt-3.5-turbo-instruct",
#             temperature=0,
#             max_retries=2,)

@mcp.tool()
async def getweather(reqeust: str) -> str:
    """A weather request tool that can be used to get weather detaisl"""

    return "it's always sunny in Lagos, Nigeria"

if __name__ == "__main__":
    # mcp.run(transport="sse")
    mcp.run()
