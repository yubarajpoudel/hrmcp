from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
import shutil
import aiofiles
from hrmcpserver import hrserver
import os
import base64
import httpx
from typing import List, Optional
import ollama

UPLOAD_DIR = "./uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/test")
async def read_root():
    return {"message": "i am alive"}

def process_chat_message(message: str) -> str:
    """
    Process a chat message using Ollama and available tools.
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
    
    
    # Initial call to the model
    response = ollama.chat(
        model="llama3.2",
        messages=messages,
        tools=available_tools,
    )
    
    # Loop to handle tool calls
    while response.message.tool_calls:
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
        
        # Get the next response from the model
        response = ollama.chat(
            model="llama3.2",
            messages=messages,
            tools=available_tools,
        )

    return response.message.content

@app.post("/chat")
async def chat(message: str = Form(...)):
    """
    Chat endpoint for HR management
     - this will accept the input from the user as a plain text, plan the action with the ollama model to execute the available tools
     - this will call the right tool based on the plan and return the result as the plain text
    """
    result = process_chat_message(message)
    return {"result": result}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), role: str = Form(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"info": "File saved successfully", "file_path": file_path , "role": role}

def chat_interface():
    print("HR Agent Chat Interface. Type 'bye' to exit.")
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["bye", "exit", "quit"]:
                print("Goodbye!")
                break
            response = process_chat_message(user_input)
            print(f"Agent: {response}")
            if "bye" in response.lower():
                print("Agent ended the conversation.")
                break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    import uvicorn
    # Mount static files
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
    uvicorn.run(app, host="0.0.0.0", port=8000)