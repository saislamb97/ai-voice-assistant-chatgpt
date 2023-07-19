import os
import json
import random
import requests
from decouple import config
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import openai
from elevenlabs import generate, stream
from elevenlabs import set_api_key
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import boto3



# Initialize FastAPI app
app = FastAPI()

# CORS - Origins
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:4173",
    "http://localhost:3000",
    "http://127.0.0.1:8000"
]

# CORS - Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Set OpenAI organization and API key
openai.organization = config("OPEN_AI_ORG")
openai.api_key = config("OPEN_AI_KEY")

# Retrieve Eleven Labs API key from environment
set_api_key(config("ELEVEN_LABS_API_KEY"))

# Define the file name for storing messages
file_name = "stored_data.json"

# Get recent messages
def get_recent_messages():
    learn_instruction = {
        "role": "system",
        "content": "Your are Bruce, a friendly assistant and the cheerful face of Team8. You are a friendly and helpful AI website assistant from Team8. You were created to provide support and assistance to customers around the clock, ensuring that they always have access to the information they need to know about Team8, such as how a team8 website assistant could help a particular type of business. You reside on the official team8 website at t, m, 8, dot, a, i."
    }

    # Initialize messages
    messages = []

    # Add Random Element
    x = random.uniform(0, 1)
    if x < 0.2:
        learn_instruction["content"] = (
            learn_instruction["content"]
            + "Your response will have some dry humor. "
        )
    elif x < 0.5:
        learn_instruction["content"] = (
            learn_instruction["content"]
            + "Your each response will not be more than 5 sentences. "
        )
    else:
        learn_instruction["content"] = (
            learn_instruction["content"]
            + "Your response will be short and precise. "
        )

    # Append instruction to message
    messages.append(learn_instruction)

    # Get last messages
    try:
        with open(file_name) as user_file:
            data = json.load(user_file)

            # Append last 5 rows of data
            if data:
                if len(data) >= 0:
                    for item in data:
                        messages.append(item)
                else:
                    for item in data[-5:]:
                        messages.append(item)
    except:
        pass

    # Return messages
    return messages

# Save messages for retrieval later on
def store_messages(request_message, response_message):
    # Get recent messages
    messages = get_recent_messages()[1:]

    # Add messages to data
    user_message = {"role": "user", "content": request_message}
    assistant_message = {"role": "assistant", "content": response_message}
    messages.append(user_message)
    messages.append(assistant_message)

    # Save the updated file
    with open(file_name, "w") as f:
        json.dump(messages, f)

# Clear the messages
def reset_messages():
    # Write an empty file
    open(file_name, "w")

# Convert audio to text using OpenAI Whisper
def convert_audio_to_text(audio_file):
    try:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        message_text = transcript["text"]
        return message_text
    except Exception as e:
        return

# Get chat response using OpenAI ChatGPT
def get_chat_response(message_input):
    messages = get_recent_messages()
    user_message = {"role": "user", "content": message_input}
    messages.append(user_message)

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages, temperature=1, max_tokens=256, top_p=1, frequency_penalty=0, presence_penalty=0
        )
        message_text = response["choices"][0]["message"]["content"]
        return message_text
    except Exception as e:
        return


# Convert text to speech using Eleven Labs API

polly_client = boto3.client('polly', region_name='us-west-2')

def convert_text_to_speech(text_content: str):
    response = polly_client.synthesize_speech(
        Engine='neural',
        LanguageCode='en-US',
        OutputFormat='mp3',
        Text=text_content,
        VoiceId='Arthur'
    )
    audio_data = response['AudioStream'].read()
    return audio_data

# def convert_text_to_speech(message):

#     voice_id = "pNInz6obpgDQGcFmaJgB"

#     audio_stream = generate(
#         text= message,
#         voice= voice_id,
#         model="eleven_monolingual_v1",
#         stream=False
#     )

#     return audio_stream

# Post bot response
@app.post("/post-audio")
async def post_audio(file: UploadFile = File(...)):
    # Convert audio to text - production
    # Save the file temporarily
    with open(file.filename, "wb") as buffer:
        buffer.write(file.file.read())
    audio_input = open(file.filename, "rb")

    # Decode audio
    message_decoded = convert_audio_to_text(audio_input)

    # Guard: Ensure output
    if not message_decoded:
        raise HTTPException(status_code=400, detail="Failed to decode audio")

    # Get chat response
    chat_response = get_chat_response(message_decoded)
    print(chat_response)

    # Store messages
    store_messages(message_decoded, chat_response)

    # Guard: Ensure output
    if not chat_response:
        raise HTTPException(status_code=400, detail="Failed chat response")

    # Convert chat response to audio
    audio_output = convert_text_to_speech(chat_response)

    # Guard: Ensure output
    if not audio_output:
        raise HTTPException(status_code=400, detail="Failed audio output")

    # Create a generator that yields chunks of data
    def iterfile():
        yield audio_output

    # Use for Post: Return output audio
    return StreamingResponse(iterfile(), media_type="application/octet-stream")


@app.get("/")
async def get_index():
    return FileResponse("frontend/index.html")

# Check health
@app.get("/health")
async def check_health():
    return {"response": "healthy"}

# Reset Conversation
@app.get("/reset")
async def reset_conversation():
    reset_messages()
    return {"response": "conversation reset"}

# # Get chat response text
# @app.get("/get-response")
# async def get_response():
#     messages = get_recent_messages()
#     response = messages[-1]["content"] if len(messages) > 1 else ""
#     return {"response": response}

# Mount static files middleware
app.mount("/", StaticFiles(directory="frontend", html=True))