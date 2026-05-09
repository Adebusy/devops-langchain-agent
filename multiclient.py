# import the multi server mcp client
from langchain_mcp_adapters.client import MultiServerMCPClient

from mcp import StdioServerParameters

import asyncio

from langchain.agents import create_agent

from langchain_openai import OpenAI, ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

stdio_server_params = StdioServerParameters(
    command= "python3",
    args=["/Users/ramalao/Documents/git/ai/project/mcp/devops-langchain-agent/servers/math_server.py"]
)

llm =ChatOpenAI()

async def main():
    print("good!!!")

if "__main__" == "__main__":
    asyncio.run(main())

