from app.services.ai_service import call_ai


def test():
    result = call_ai(
        prompt="Say hello in one short sentence."
    )

    print("\n=== AI RESULT ===")
    print(result)


if __name__ == "__main__":
    test()