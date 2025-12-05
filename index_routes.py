from fastapi import APIRouter, FastAPI, Form, UploadFile, File, HTTPException, Request
from core.env.env_utils import get_settings
from auth.redis_handler import RedisHandler

settings = get_settings()
import shutil
import aiofiles
from hrmcpserver import hrserver
import base64
import httpx
from typing import List, Optional
import ollama
from fastapi import Depends
from middleware import auth_middleware
from auth.user_utils import get_current_user
from fastapi.responses import StreamingResponse
import json

router = APIRouter(
    prefix="",
    tags=["index"],
)

UPLOAD_DIR = "./uploads/"
redis_client = RedisHandler.get_instance()

def llm_token_limit_middleware(key: str, body_str: str):
    print("llm middleware - IP: {key}, body: {body_str}")  
    llm_token_size = int(len(body_str) // 4 if body_str else 0)
    
    print(f"llm middleware - IP: {key}, estimated tokens: {llm_token_size}")

    if llm_token_size > settings.LLM_TOKEN_LIMIT:
        raise HTTPException(status_code=403, detail="Input text is too long, increase your plan to allow more tokens")
    
    token_usage_str = redis_client.get_key(key)
    token_usage_count = int(token_usage_str) if token_usage_str else 0
    
    remaining_allowed_token = settings.LLM_TOKEN_LIMIT - token_usage_count

    if remaining_allowed_token < llm_token_size:
        raise HTTPException(status_code=403, detail="Token limit has reached its max limit")
    else:
        new_usage = token_usage_count + llm_token_size
        redis_client.set_key(key, str(new_usage))



def process_chat_message(message: str):
    """
    Process a chat message using Ollama and available tools.
    Returns a generator that yields response chunks.
    """
    """ System prompt to inform the model about the tool is usage """
    system_message = {
        "role": "system", 
        "content": f""" You are a HR management assistant. You can do following actions:
                   - read or extract text from image using 'mcp/hr/read_resume_from_file' 
                   - candidate screening or review cv using 'mcp/hr/candidate_screening'
                   - can get available time slots using 'mcp/hr/get_interviewer_free_time' and 
                   - can schedule an interview using 'mcp/hr/schedule_interview' if needed.

                   Response format:
                   - if you need to perform an action, CALL THE TOOL DIRECTLY. Do not describe what you are going to do, just call the tool.
                   - if you have the final answer, provide formatted response for eg. "based on your input, here is the final summar \n <final answer>".
                   - structure the response with proper paragraph and list and heading.
                   - if the action is not clear, provide a text response.
                   - if you need to ask the user a clarifying question, provide a text response.

                Important Note: donot include tool call in the response. just provide the final answer.
                   """
    }
    # User asks a question
    user_message = {
        "role": "user", 
        "content": message
    }
    messages = [system_message, user_message]
    available_tools = [ hrserver.read_resume_from_file, hrserver.candidate_screening, hrserver.get_interviewer_free_time , hrserver.schedule_interview]
    
    while True:
        # Initial call to the model (non-streaming to handle tools correctly)
        response = ollama.chat(
            model="llama3.2",
            messages=messages,
            tools=available_tools,
            stream=False
        )
        
        if response.message.tool_calls:
            # Add the assistant's message with tool calls to history
            messages.append(response.message)
            
            tool_map = {tool.__name__: tool for tool in available_tools}
            
            for tool_call in response.message.tool_calls:
                print(f"Tool called: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
                func = tool_map.get(tool_call.function.name)
                if func:
                    try:
                        result = func(**tool_call.function.arguments)
                        # Add the tool result to history
                        messages.append({
                            "role": "tool",
                            "content": str(result),
                        })
                    except Exception as e:
                        messages.append({
                            "role": "tool",
                            "content": f"Error executing tool {tool_call.function.name}: {str(e)}",
                        })
            # Loop again to let the model process tool results
        else:
            # No tool calls, this is the final response.
            # Re-run with stream=True to stream the content to the user.
            stream = ollama.chat(
                model="llama3.2",
                messages=messages,
                tools=available_tools,
                stream=True
            )
            
            for chunk in stream:
                content = chunk['message']['content']
                if content:
                    yield content
            break

def chat_interface():
    print("HR Agent Chat Interface. Type 'bye' to exit.")
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["bye", "exit", "quit"]:
                print("Goodbye!")
                break
            
            # For CLI, we just consume the generator and print
            print("Agent: ", end="", flush=True)
            full_response = ""
            for chunk in process_chat_message(user_input):
                print(chunk, end="", flush=True)
                full_response += chunk
            print()
            
            if "bye" in full_response.lower():
                print("Agent ended the conversation.")
                break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")


@router.post("/chat")
def chat(req: Request, message: str = Form(...), current_user = Depends(get_current_user)):
    """
    Chat endpoint for HR management
     - this will accept the input from the user as a plain text, plan the action with the ollama model to execute the available tools
     - this will call the right tool based on the plan and return the result as the plain text
    """
    llm_token_limit_middleware(current_user.id, message)
    
    return StreamingResponse(
        process_chat_message(message),
        media_type="text/event-stream"
    )

@router.post("/upload")
def upload_file(file: UploadFile = File(...), role: str = Form(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"info": "File saved successfully", "file_path": file_path , "role": role}

@router.get("/test")
def read_root():
    return {"message": "i am alive"}