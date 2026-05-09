from langchain_openai import OpenAI


def generate_terraform(user_request: str) -> str:
    """
    This is a terraform tool {user_request} proposed to help generate terraform template and 
    used for troubleshooting terraform related issues
    """
    request = OpenAI(model="gpt-3.5-turbo-instruct",temperature=0, max_retries=2,)

    request.invoke(user_request)
