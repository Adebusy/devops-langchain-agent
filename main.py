from dotenv import load_dotenv 
import asyncio
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
load_dotenv()

llm =ChatOpenAI()

stdio_server_params = StdioServerParameters(
    command= "python3",
    args=["/Users/ramalao/Documents/git/ai/project/mcp/devops-langchain-agent/servers/math_server.py"]
)

async def main():
    async with stdio_client(stdio_server_params) as (read, write):
        async with ClientSession(read_stream=read, write_stream=write) as session:
            await session.initialize()

            tools = await load_mcp_tools(session)
            
            agent = create_agent(llm, tools)

            result = await agent.ainvoke({"messages":[HumanMessage(content="what is 2 + 2?")]})
            print(result["messages"][-1].content)
if __name__ == "__main__":
    asyncio.run(main())
