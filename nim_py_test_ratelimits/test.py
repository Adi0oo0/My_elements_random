import logging
import threading
import time
from itertools import cycle
from typing import List, Dict, Any, Optional

from openai import OpenAI

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_WORKER_CONCURRENCY = 31
BASE_URL = "https://integrate.api.nvidia.com/v1"
API_KEYS = [
    "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",
    "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",
    "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"
]

# -----------------------------------------------------------------------------
# Core Classes
# -----------------------------------------------------------------------------
class RateLimiter:
    """
    A thread-safe rate limiter to guarantee a minimum delay between API calls.
    """
    def __init__(self, delay_seconds: float):
        self.delay = delay_seconds
        self.lock = threading.Lock()
        self.last_call = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_call = time.time()


class NvidiaNIMClient:
    """
    Client to interact with NVIDIA's NIM API using standard Chat Completions
    and Automatic API Key Rotation.
    """
    def __init__(self, base_url: str, api_keys: List[str]) -> None:
        self.base_url = base_url
        self._worker_semaphore = threading.BoundedSemaphore(MAX_WORKER_CONCURRENCY)
        self._rate_limiter = RateLimiter(delay_seconds=1.5)
        
        # Round-robin key rotation to maximize throughput and avoid limits
        self._api_key_pool = cycle(api_keys)
        
        # Core Generation Parameters
        self.model = 'z-ai/glm-5.2'
        self.temperature = 1.0
        self.top_p = 0.95
        self.max_tokens = 16384
        self.stream = False
        self.thinking = True
        self.reasoning_budget = 16384
        
        # Maintain proper conversation history as per OpenAI specification
        self.chat_history: List[Dict[str, str]] = []

    def _get_client(self) -> OpenAI:
        """Instantiates a client dynamically using the next available API key."""
        return OpenAI(
            base_url=self.base_url,
            api_key=next(self._api_key_pool)
        )

    def clear_history(self) -> None:
        """Wipes the conversation memory."""
        self.chat_history.clear()

    def generate_response(self, prompt: str, role: str = 'user') -> Optional[Dict[str, Any]]:
        """
        Submits the prompt, maintains history, and safely extracts telemetry.
        """
        # 1. Append the new user prompt to the ongoing chat history
        self.chat_history.append({"role": role, "content": prompt})
        
        self._worker_semaphore.acquire()
        try:
            # 2. Enforce global rate limit across all active threads
            self._rate_limiter.wait()
            
            # 3. Get a client instance with a rotated key
            client = self._get_client()
            
            # 4. Make the API Call
            completion = client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": self.thinking},
                    "reasoning_budget": self.reasoning_budget
                },
                stream=self.stream
            )
            
            response_message = completion.choices[0].message
            
            # 5. Save the assistant's response back to history for context
            if response_message.content:
                self.chat_history.append({
                    "role": "assistant", 
                    "content": response_message.content
                })

            # 6. Safely extract standard metrics and NVIDIA custom telemetry
            nvext = getattr(completion, 'nvext', {})
            scheduler_snapshot = nvext.get('scheduler_snapshot', {})
            request_throughput = nvext.get('request_throughput', {})
            usage = completion.usage

            return {

                'content': response_message.content,
                'reasoning_content': getattr(response_message, 'reasoning_content', 'No reasoning provided.'),
                'model': completion.model,
                'completion_tokens': usage.completion_tokens if usage else 0,
                'prompt_tokens': usage.prompt_tokens if usage else 0,
                'total_tokens': usage.total_tokens if usage else 0,
                'n_running_req': scheduler_snapshot.get('num_running_reqs', 0),
                'n_waiting_req': scheduler_snapshot.get('num_waiting_reqs', 0),
                'e2e_latency': request_throughput.get('e2e_latency_seconds', 0.0),
                'tokens_per_sec': request_throughput.get('generation_tokens_per_second', 0.0)
            }

        except Exception as e:
            logger.error(f"API Request failed: {e}")
            # If the request fails, remove the user's prompt so it isn't stuck in history without a response
            if self.chat_history:
                self.chat_history.pop()
            return None
            
        finally:
            self._worker_semaphore.release()

# -----------------------------------------------------------------------------
# Main Execution Loop
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    # Initialize a single client manager that handles its own history and keys
    client_manager = NvidiaNIMClient(base_url=BASE_URL, api_keys=API_KEYS)
    
    print("=" * 60)
    print(" NVIDIA NIM Chat Session Initialized")
    print(" Commands: 'exit' to quit | 'clear' to wipe context")
    print("=" * 60)
    
    while True:
        try:
            user_prompt = input('\nUser: ').strip()
            
            if not user_prompt:
                continue
            if user_prompt.lower() == 'exit':
                print("Ending session...")
                break
            if user_prompt.lower() == 'clear':
                client_manager.clear_history()
                print("\n[System]: Conversation context wiped. Starting fresh.\n")
                continue

            response = client_manager.generate_response(user_prompt)
            
            if response:
                print(f"\n--- Reasoning ---\n{response.get('reasoning_content')}")
                print(f"\n--- Response ---\n{response.get('content')}")
                print(f"\n[Telemetry]: {response.get('tokens_per_sec'):.2f} tokens/s | Latency: {response.get('e2e_latency'):.2f}s")
            else:
                print("\n[!] Failed to generate a response. Please try again.")
                
        # Gracefully handle Ctrl+C
        except KeyboardInterrupt:
            print("\nSession interrupted by user. Exiting...")
            break








'''

while True:
  usr_prompt = input('User: ')
  if usr_prompt == 'exit':
    break

  completion = client.chat.completions.create(
    model="nvidia/nemotron-3-ultra-550b-a55b",
    messages=[{"role":"user","content":usr_prompt if usr_prompt is not None else 'Hello'}],
    temperature=1,
    top_p=0.95,
    max_tokens=16384,
    extra_body={"chat_template_kwargs":{"enable_thinking":True},"reasoning_budget":16384},
    stream=False      # always false due to inference limitations
  )
  print('Reasoning: ', completion.choices[0].message.reasoning_content, '\n')
  
  print('Response: ', completion.choices[0].message.content)

'''

'''
stream: False
  {"id":"chatcmpl-364d9ff4-fe68-414f-af70-b8fd25a47ada","choices":[{"finish_reason":"stop","index":0,"logprobs":null,"message":{"content":"Hi there! How can I help you today?","refusal":null,"role":"assistant","annotations":null,"audio":null,"function_call":null,"tool_calls":null,"reasoning_content":"The user said \"hi\". This is a standard greeting.\nI should respond with a friendly greeting and offer assistance."}}],"created":1786036661,"model":"nvidia/nemotron-3-ultra-550b-a55b","object":"chat.completion","moderation":null,"service_tier":null,"system_fingerprint":null,"usage":{"completion_tokens":35,"prompt_tokens":17,"total_tokens":52,"completion_tokens_details":null,"prompt_tokens_details":null},"nvext":{"scheduler_snapshot":{"num_running_reqs":18,"num_waiting_reqs":0},"request_throughput":{"e2e_latency_seconds":0.7076699733734131,"generation_tokens_per_second":49.45808260474506,"draft_tokens_per_second":0.0}}}

# stream: True
# {"id":"chatcmpl-ff30fa38-e6ea-4443-9448-659f131fc6e1","choices":[{"delta":{"content":null,"function_call":null,"refusal":null,"role":"assistant","tool_calls":null,"reasoning_content":"The"},"finish_reason":null,"index":0,"logprobs":null}],"created":1786110612,"model":"nvidia/nemotron-3-ultra-550b-a55b","object":"chat.completion.chunk","moderation":null,"service_tier":null,"system_fingerprint":null,"usage":null}
'''