import logging
import threading
import time
import sys
from itertools import cycle
from typing import List, Dict, Any, Optional, Generator

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
    Client to interact with NVIDIA's NIM API using standard Chat Completions,
    Automatic API Key Rotation, and robust Streaming support.
    """
    def __init__(self, base_url: str, api_keys: List[str]) -> None:
        self.base_url = base_url
        self._worker_semaphore = threading.BoundedSemaphore(MAX_WORKER_CONCURRENCY)
        self._rate_limiter = RateLimiter(delay_seconds=1.5)
        
        self._api_key_pool = cycle(api_keys)
        
        self.model = 'nvidia/nemotron-3-ultra-550b-a55b'
        self.temperature = 1.0
        self.top_p = 0.95
        self.max_tokens = 16384
        self.stream = True  # Set to True by default now
        self.thinking = True
        self.reasoning_budget = 16384
        
        self.chat_history: List[Dict[str, str]] = []

    def _get_client(self) -> OpenAI:
        return OpenAI(
            base_url=self.base_url,
            api_key=next(self._api_key_pool)
        )

    def clear_history(self) -> None:
        self.chat_history.clear()

    def generate_response(self, prompt: str, role: str = 'user') -> Optional[Dict[str, Any]]:
        """
        Synchronous (Non-Streaming) Generation.
        """
        self.chat_history.append({"role": role, "content": prompt})
        self._worker_semaphore.acquire()
        
        try:
            self._rate_limiter.wait()
            client = self._get_client()
            
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
                stream=False
            )
            
            response_message = completion.choices[0].message
            if response_message.content:
                self.chat_history.append({"role": "assistant", "content": response_message.content})

            nvext = getattr(completion, 'nvext', {})
            request_throughput = nvext.get('request_throughput', {})

            return {
                'content': response_message.content,
                'reasoning_content': getattr(response_message, 'reasoning_content', 'No reasoning provided.'),
                'tokens_per_sec': request_throughput.get('generation_tokens_per_second', 0.0),
                'e2e_latency': request_throughput.get('e2e_latency_seconds', 0.0)
            }

        except Exception as e:
            logger.error(f"API Request failed: {e}")
            if self.chat_history: self.chat_history.pop()
            return None
        finally:
            self._worker_semaphore.release()

    def stream_response(self, prompt: str, role: str = 'user') -> Generator[Dict[str, str], None, None]:
        """
        Asynchronous (Streaming) Generation. Yields chunks as they arrive.
        """
        self.chat_history.append({"role": role, "content": prompt})
        self._worker_semaphore.acquire()
        
        full_content = []
        
        try:
            self._rate_limiter.wait()
            client = self._get_client()
            
            stream = client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": self.thinking},
                    "reasoning_budget": self.reasoning_budget
                },
                stream=True
            )
            
            for chunk in stream:
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Yield Reasoning (Thinking) chunks
                reasoning = getattr(delta, 'reasoning_content', None)
                if reasoning:
                    yield {"type": "reasoning", "delta": reasoning}
                
                # Yield Standard Content chunks
                content = delta.content
                if content:
                    full_content.append(content)
                    yield {"type": "content", "delta": content}
            
            # Save the fully assembled text to history for future context
            final_content = "".join(full_content)
            if final_content:
                self.chat_history.append({"role": "assistant", "content": final_content})

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            if self.chat_history: self.chat_history.pop()
            yield {"type": "error", "delta": str(e)}
        finally:
            self._worker_semaphore.release()


# -----------------------------------------------------------------------------
# Main Execution Loop
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    client_manager = NvidiaNIMClient(base_url=BASE_URL, api_keys=API_KEYS)
    
    print("=" * 65)
    print(" NVIDIA NIM Chat Session Initialized")
    print(" Commands: 'exit' | 'clear' | 'toggle-stream'")
    print("=" * 65)
    
    while True:
        try:
            user_prompt = input('\nUser: ').strip()
            
            if not user_prompt: continue
            if user_prompt.lower() == 'exit':
                print("Ending session...")
                break
            if user_prompt.lower() == 'clear':
                client_manager.clear_history()
                print("\n[System]: Conversation context wiped. Starting fresh.\n")
                continue
            if user_prompt.lower() == 'toggle-stream':
                client_manager.stream = not client_manager.stream
                status = 'ON' if client_manager.stream else 'OFF'
                print(f"\n[System]: Streaming mode is now {status}.\n")
                continue

            # --- STREAMING MODE ---
            if client_manager.stream:
                print("\n--- Generating ---")
                is_reasoning = False
                is_answering = False
                
                for chunk in client_manager.stream_response(user_prompt):
                    if chunk['type'] == 'error':
                        print(f"\n[!] Error: {chunk['delta']}")
                        break
                        
                    elif chunk['type'] == 'reasoning':
                        if not is_reasoning:
                            print("\n[Thinking...]\n", end="", flush=True)
                            is_reasoning = True
                        print(chunk['delta'], end="", flush=True)
                        
                    elif chunk['type'] == 'content':
                        if not is_answering:
                            print("\n\n[Response]\n", end="", flush=True)
                            is_answering = True
                        print(chunk['delta'], end="", flush=True)
                
                print("\n") # formatting newline at the very end
                
            # --- STATIC/SYNC MODE ---
            else:
                response = client_manager.generate_response(user_prompt)
                if response:
                    print(f"\n--- Reasoning ---\n{response.get('reasoning_content')}")
                    print(f"\n--- Response ---\n{response.get('content')}")
                    print(f"\n[Telemetry]: {response.get('tokens_per_sec'):.2f} tokens/s | Latency: {response.get('e2e_latency'):.2f}s")
                else:
                    print("\n[!] Failed to generate a response. Please try again.")

        except KeyboardInterrupt:
            print("\nSession interrupted by user. Exiting...")
            break












# def func(x):
#     for i in range(x):
#         yield x**i


# print([i for i in func(4)])

# def func2():
#         re_dict = dict()
#         for chunk in completion:
#             if not chunk.choices:
#               continue
#             reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
#             if reasoning:
#               re_dict['reasoning'] = reasoning
#             if chunk.choices[0].delta.content is not None:
#               re_dict['content'] = chunk.choices[0].delta.conte
#             yield re_dict
            
# response = m.response()
# while True:
#     print(response['content'])
#     print(response['reasoning'])