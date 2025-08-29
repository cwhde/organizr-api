# app.py

import telebot
import openai
import tiktoken
import logging
import api
import os
import json
from datetime import datetime

# Env vars from docker compose
telegram_key = os.environ.get('TELEGRAM_API_KEY')
openai_key = os.environ.get('OPENAI_API_KEY')
openai_baseurl = os.environ.get('OPENAI_BASE_URL')
openai_model = os.environ.get('OPENAI_MODEL')

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup telegram
logger.info("Initializing Telegram API")
organizr_bot = telebot.TeleBot(telegram_key)

# Setup openapi compatible LLM
logger.info("Initializing LLM API")
llm = openai.OpenAI(
    base_url=openai_baseurl,
    api_key=openai_key
)

def run_bot():
    """Start the telegram bot with checks, preparations and then the final infinite polling"""
    logger.info("Checking API health")
    if not api.check_health():
        logger.error("API health check failed. Bot will not start.")
        return
    
    logger.info("Checking if organizrbot app exists in API")
    apps = api.list_apps()
    app_names = [app.get("name") for app in apps] if isinstance(apps, list) else []
    if "organizrbot" not in app_names:
        logger.info("App not found. Creating new app 'organizrbot'")
        try:
            api.create_app("organizrbot")
        except Exception as e:
            logger.error(f"Failed to create app: {e}")
            return
            
    logger.info("Ensuring admin user is registered in organizrbot app")
    if not api.check_user_exists_in_app("admin"):
        logger.info("Admin user not found in API. Creating and linking admin.")
        api.create_and_link_user("admin")
        
    logger.info("Starting Telegram polling")
    organizr_bot.infinity_polling()


@organizr_bot.message_handler(func=lambda message: True)
def message_entrypoint(message):
    """Handles all incoming messages, checks user registration, and passes to the main logic."""
    user_id_str = str(message.from_user.id)
    logger.info(f"Received message from Telegram user ID {user_id_str}")

    try:
        if not api.check_user_exists_in_app(user_id_str):
            logger.info(f"User {user_id_str} not found in API. Creating new user and link.")
            api.create_and_link_user(user_id_str)
            organizr_bot.send_message(message.chat.id, "✅ *Welcome\\!* You have been successfully registered as a new user\\.", parse_mode='MarkdownV2')
        
        # Proceed to actually handle the message
        handle_message(message)
    except Exception as e:
        logger.error(f"An error occurred while handling message for user {user_id_str}: {e}", exc_info=True)
        organizr_bot.send_message(message.chat.id, "❌ _Sorry, an unexpected error occurred\\. Please try again later\\._", parse_mode='MarkdownV2')

def normalize_message_obj(m):
    """
    Return a JSON-serializable dict for a message-like object.
    Accepts:
      - plain dicts (returned unchanged)
      - pydantic/OpenAI response objects (via model_dump/model_dump_json/.dict)
      - simple objects with attributes (role, content, name, id, tool_calls, ...)
    """
    if isinstance(m, dict):
        return m
    # pydantic v2 style
    if hasattr(m, "model_dump"):
        try:
            return m.model_dump(mode="json")
        except Exception:
            # fallback
            return m.model_dump() if hasattr(m, "model_dump") else dict()
    # older pydantic / other object fallback
    if hasattr(m, "dict"):
        try:
            return m.dict()
        except Exception:
            pass
    # last resort: pull likely attributes
    out = {}
    for attr in ("role", "content", "name", "id", "tool_call_id", "tool_calls"):
        if hasattr(m, attr):
            out[attr] = getattr(m, attr)
    # if content is a nested pydantic model list/obj, try to serialize
    try:
        json.dumps(out)  # test-serializable
        return out
    except Exception:
        # as a final fallback return stringified object for content
        return {"role": getattr(m, "role", "assistant"), "content": str(getattr(m, "content", m))}
    
def handle_message(msg):
    """Main logic to process a message: load history, call LLM, handle tools, and save history."""
    telegram_id = str(msg.from_user.id)
    chat_id = msg.chat.id

    # Get internal API user ID
    internal_user_id = api.id_to_internal(telegram_id)
    if not internal_user_id:
        logger.error(f"Could not translate telegram ID {telegram_id} to internal ID.")
        organizr_bot.send_message(chat_id, "❌ _There was an issue identifying your user account\\. Cannot proceed\\._", parse_mode='MarkdownV2')
        return
    
    admin_internal_id = api.id_to_internal("admin")
    if not admin_internal_id:
        logger.error("Could not find internal ID for admin user.")
        organizr_bot.send_message(chat_id, "❌ *Critical error:* _Admin account not found\\. Please contact the administrator\\._", parse_mode='MarkdownV2')
        return

    # Load chat history
    logger.info(f"Loading chat history for user {internal_user_id} (from Telegram ID {telegram_id})")
    notes_response = api.get_notes(for_user=admin_internal_id, title=telegram_id)
    
    messages = []
    note_id = None
    if notes_response and isinstance(notes_response, list) and len(notes_response) > 0:
        if len(notes_response) > 1:
            logger.warning(f"Found multiple chat history notes for user {telegram_id}. Using the first one.")
        note = notes_response[0]
        note_id = note.get("id")
        try:
            content = note.get("content", "[]")
            if content:
                messages = json.loads(content)
                if not isinstance(messages, list):
                    logger.warning(f"Chat history for user {telegram_id} is not a list. Resetting.")
                    messages = []
        except (json.JSONDecodeError, TypeError):
            logger.error(f"Failed to parse chat history for user {telegram_id}. Starting fresh.")
            messages = []
    else:
        logger.info(f"No chat history note found for user {telegram_id}. A new one will be created.")

    # Truncate messages to fit token limit
    messages = truncate_messages(messages)

    # Add system message at start and user message at end
    messages.insert(0, {"role": "system", "content": get_system_message(msg, internal_user_id)})
    messages.append({"role": "user", "content": msg.text})

    # Main loop for LLM interaction and tool calls
    while True:
        try:
            logger.info(f"Sending request to LLM for user {internal_user_id}. Message count: {len(messages)}")
            request = llm.chat.completions.create(
                model=openai_model,
                messages=messages,
                tools=api.functions,
                temperature=0.2,
                # tool_choice="auto" is default
            )
            response_message = request.choices[0].message
            response_message_dict = normalize_message_obj(response_message)
            messages.append(response_message_dict)

            tool_calls = None
            if hasattr(response_message, "tool_calls"):
                tool_calls = getattr(response_message, "tool_calls")
            else:
                tool_calls = response_message_dict.get("tool_calls")


            if tool_calls:
                logger.info(f"LLM requested {len(tool_calls)} tool call(s).")
                for tool_call in tool_calls:
                    fn_name = getattr(tool_call.function, "name", None) or tool_call.get("function", {}).get("name")
                    args_str = getattr(tool_call.function, "arguments", None) or tool_call.get("function", {}).get("arguments")
                    logger.info(f"Executing tool: {fn_name}({args_str})")
                    try:
                        function_to_call = getattr(api, fn_name)
                        args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
                        if "for_user" in function_to_call.__code__.co_varnames:
                            args['for_user'] = internal_user_id
                        result = function_to_call(**args)
                    except AttributeError:
                        logger.error(f"Function {fn_name} not found in api.py.")
                        result = f"Error: Function {fn_name} not found."
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in arguments: {args_str}")
                        result = "Error: Invalid function arguments format."
                    except Exception as e:
                        logger.error(f"Error executing function {fn_name}({args_str}): {e}", exc_info=True)
                        result = f"Error: {e}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": getattr(tool_call, "id", tool_call.get("id") if isinstance(tool_call, dict) else None),
                        "name": fn_name,
                        "content": str(result)
                    })
                    
                    # Let the user know what tool is being executed
                    result_str = str(result)
                    organizr_bot.send_message(chat_id, f"```\n⚙️ Executed: {fn_name}(...)\n\nResult:\n{result_str[:200]}\n```", parse_mode='MarkdownV2')

            else:
                # No more tool calls, final answer
                final_content = response_message_dict.get("content") or response_message_dict.get("text") or ""
                logger.info(f"Final response for user {internal_user_id}: \"{final_content}\"")

                # Save all messages that arent the dynamic system message
                messages_to_store = [m for m in messages if m.get("role") != "system"]

                if note_id:
                    api.update_note(note_id=note_id, new_content=json.dumps(messages_to_store))
                else:
                    api.create_note(for_user=admin_internal_id, title=telegram_id, content=json.dumps(messages_to_store))
                
                organizr_bot.reply_to(msg, final_content, parse_mode='MarkdownV2')
                break

        except Exception as e:
            logger.error(f"An error occurred in the LLM loop for user {internal_user_id}: {e}", exc_info=True)
            organizr_bot.send_message(chat_id, "❌ _An error occurred while processing your request\\. Please try again\\._", parse_mode='MarkdownV2')
            break


def get_system_message(msg, internal_user_id):
    """Generates the detailed system message for the LLM."""
    base_message = """You are organizr-bot, a helpful and efficient Telegram Bot acting as a personal assistant for the user. Your main purpose is to interact with the organizr-api to manage the user's notes, tasks, and calendar events.

### Your Persona:
- You are **casual, friendly, and conversational**. Use a tone appropriate for a chat app.
- You are **proactive and helpful**. If a user's request is ambiguous, ask for clarification.
- You are **concise**. Get to the point, but be polite.
- When writing, you format messages using Telegram's MarkdownV2 format, which has specific escaping rules you must follow.

### MarkdownV2 Formatting Rules:
You MUST follow these exact escaping rules for MarkdownV2:
- **Bold text**: `*bold text*` (asterisks must NOT be escaped when used for formatting)
- **Italic text**: `_italic text_` (underscores must NOT be escaped when used for formatting)  
- **Underlined text**: `__underlined text__` (double underscores must NOT be escaped when used for formatting)
- **Strikethrough**: `~strikethrough~` (tildes must NOT be escaped when used for formatting)
- **Spoiler**: `||spoiler||` (double pipes must NOT be escaped when used for formatting)
- **Inline code**: `` `code` `` (backticks must NOT be escaped when used for formatting)
- **Code blocks**: Use triple backticks ``` without escaping them

**CRITICAL**: The following characters MUST be escaped with a backslash when they appear in regular text (not as formatting):
`_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`

**Examples of correct escaping:**
- Regular text with special chars: `This costs $5\.99\!` 
- Bold text: `*This is bold*` (no escaping needed for formatting asterisks)
- Mixed: `*Bold text* costs $5\.99\!` (escape special chars in regular text, not formatting chars)
- Links: `[Google](https://google\.com)` (escape dots in URLs but not the bracket/parenthesis syntax)
- Lists: Use `•` bullet character instead of `*` or `-` to avoid conflicts

Always apply these rules consistently to ensure proper message rendering.

### Core Task:
Your goal is to understand the user's natural language request and translate it into one or more tool calls to the organizr-api. You MUST use the provided tools to fulfill requests related to notes, tasks, and calendar.

### Tool Usage Guidelines:
- **Always use tools** to create, read, update, or delete (CRUD) user data. Do not invent information.
- When creating or updating items (notes, tasks, events), use the information provided by the user. Be professional and clear in the content you generate for these items, unless the user specifies a different style.
- When querying for information (`get_notes`, `get_tasks`, `query_events`), present the results to the user in a clean, readable format (e.g., using lists). If no results are found, inform the user clearly.
- You can chain multiple tool calls. For example, a user might ask to "find the note about the project and add a new task to it." This would require a `get_notes` call first, followed by a `create_task` call.
- The user is automatically informed about tool calls happening in the background, so you do not need to say "I am now calling the function...". You can simply state the result after the tool has been called.
- If the user references something that you never heard about, you can also use the tools to provide context to yourself: You can query the users notes, tasks and calendar to find any needed information you need for yourself, tool calls aren't limited to providing aid to the user.

### Important Context:
- The current date and time is: **$DATETIME**.
- The user's first name is: **$USERNAME**.
- You are operating on behalf of the user with internal API ID: **$ORGANIZRID**. You do not need to mention this ID to the user. All your tool calls will be automatically associated with this user."""

    return base_message.replace("$DATETIME", datetime.now().strftime("%d.%m.%Y %H:%M:%S")) \
        .replace("$USERNAME", msg.from_user.first_name) \
        .replace("$ORGANIZRID", internal_user_id)

def truncate_messages(messages, max_tokens=32000):
    """Removes messages from the beginning of the list until the total token count is below the max."""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        enc = tiktoken.encoding_for_model("gpt-4o") # Fallback

    total_tokens = 0
    for msg in messages:
        total_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in msg.items():
            total_tokens += len(enc.encode(str(value)))
            if key == "name":  # if there's a name, the role is omitted
                total_tokens -= 1  # role is 1 token

    while total_tokens > max_tokens:
        if not messages:
            break
        removed_message = messages.pop(0)
        
        # Recalculate tokens removed
        removed_tokens = 4
        for key, value in removed_message.items():
            removed_tokens += len(enc.encode(str(value)))
            if key == "name":
                removed_tokens -= 1
        total_tokens -= removed_tokens
        logger.info(f"Truncating history. Removed one message to save ~{removed_tokens} tokens. New total: {total_tokens}")

    return messages

if __name__ == '__main__':
    run_bot()