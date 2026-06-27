import os
import time
from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIStatusError

load_dotenv()

client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

QUESTION = "What is the capital of France? Answer in one sentence."

MODELS = [
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-120b:free",
]

# Price per million tokens (USD). Free-tier models are $0.
PRICES = {
    "google/gemma-4-31b-it:free":  {"in": 0.0, "out": 0.0},
    "openai/gpt-oss-120b:free":    {"in": 0.0, "out": 0.0},
}

REQUEST_TIMEOUT = 30  # seconds

def ask(question: str, model: str) -> dict:
    try:
        start = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            max_tokens=256,
            timeout=REQUEST_TIMEOUT,
        )
        latency = time.perf_counter() - start

        answer = response.choices[0].message.content or "(no content returned)"
        usage = response.usage
        in_tok  = usage.prompt_tokens     if usage else 0
        out_tok = usage.completion_tokens if usage else 0

        price = PRICES.get(model, {"in": 0.0, "out": 0.0})
        cost = (in_tok * price["in"] + out_tok * price["out"]) / 1_000_000

        return {
            "answer":  answer,
            "latency": latency,
            "in_tok":  in_tok,
            "out_tok": out_tok,
            "cost":    cost,
        }
    except APITimeoutError:
        return {"error": f"timed out after {REQUEST_TIMEOUT}s"}
    except APIStatusError as e:
        return {"error": f"API error {e.status_code}: {e.message}"}
    except Exception as e:
        return {"error": str(e)}

def short_name(model: str) -> str:
    return model.split("/")[-1].replace(":free", "")

def print_comparison(question: str, results: list) -> None:
    COL     = 36   # column width for each model
    PREVIEW = 32   # max answer chars before truncation
    SEP     = "  "
    ruler   = "-" * (10 + (COL + len(SEP)) * len(results))

    def row(label, values):
        cells = SEP.join(f"{str(v):<{COL}}" for v in values)
        print(f"{label:<10}{cells}")

    def preview(r):
        if "error" in r:
            return ("ERROR: " + r["error"])[:COL]
        text = r["answer"].replace("\n", " ")
        return text[:PREVIEW] + ("…" if len(text) > PREVIEW else "")

    print(f"\nQuestion: {question}\n")
    print(ruler)
    row("Model",   [short_name(m)                              for m, _ in results])
    print(ruler)
    row("Answer",  [preview(r)                                 for _, r in results])
    row("Latency", [f"{r['latency']:.2f}s" if "error" not in r else "—" for _, r in results])
    row("Tokens",  [f"{r['in_tok']} in / {r['out_tok']} out"  if "error" not in r else "—" for _, r in results])
    row("Cost",    [f"${r['cost']:.6f}"                        if "error" not in r else "—" for _, r in results])
    print(ruler)

if __name__ == "__main__":
    results = [(model, ask(QUESTION, model)) for model in MODELS]
    print_comparison(QUESTION, results)
