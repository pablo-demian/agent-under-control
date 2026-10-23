from openai import OpenAI

MODEL = "gpt-5.4-mini"

client = OpenAI(timeout=30.0, max_retries=1)

try:
    response = client.responses.create(
        model=MODEL,
        instructions=(
            "You are a component of an AI reliability "
            "engineering research laboratory. "
            "Follow the user's instructions precisely."
        ),
        input=(
            "Respond with exactly this text: "
            "Agent Under Control - READY"
        ),
        max_output_tokens=100,
    )

    print("\n=== AGENT UNDER CONTROL ===")
    print("Response:", response.output_text)
    print("Model:", response.model)
    print("Input tokens:", response.usage.input_tokens)
    print("Output tokens:", response.usage.output_tokens)
    print("Total tokens:", response.usage.total_tokens)
    print("Status:", response.status)

except Exception as e:
    print(f"\nAPI ERROR: {type(e).__name__}: {e}")
    raise SystemExit(1)
