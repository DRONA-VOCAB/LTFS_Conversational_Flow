"""CLI version of the survey bot"""

from app.flow.flow_manager import get_question_text, process_answer
from app.sessions.session_schema import create_session
from app.sessions.session_store import save_session, get_session
import sys


def main():
    print("=" * 60)
    print("L and T Finance Customer Survey Bot")
    print("=" * 60)
    print()

    # Get customer name
    customer_name = input("Enter customer name: ").strip()
    if not customer_name:
        customer_name = "Customer"

    # Create session
    session_id = "test_session_001"
    session = create_session(session_id, customer_name)
    save_session(session)

    print(f"\nSession started for {customer_name}")
    print("-" * 60)
    print()

    # Main conversation loop
    while True:
        # Get current question
        question_text = get_question_text(session)

        if question_text is None:
            print("\n" + "=" * 60)
            print("Survey completed! Thank you for your time.")
            print("=" * 60)
            break

        # Display question
        print(f"Bot: {question_text}")
        print()

        # Get user input
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit", "end"]:
                print("\nSession ended by user.")
                break

            if not user_input:
                print("Please provide an answer.")
                continue

        except KeyboardInterrupt:
            print("\n\nSession interrupted.")
            break
        except EOFError:
            print("\n\nSession ended.")
            break

        # Process answer
        result = process_answer(session, user_input)
        save_session(session)

        print()

        if result == "END":
            print("Maximum retries exceeded. Session ended.")
            break
        elif result == "REPEAT":
            print("(Please provide a clearer answer)")
            print()
        elif result == "COMPLETED":
            print("=" * 60)
            if session.get("call_should_end"):
                print("Dhanyawad aapke samay ke liye.")
                print(
                    "Hum aapke dwara bataye gaye samay par customer se sampark karenge."
                )
                print("Aapka din shubh ho!")
            else:
                print("Survey completed! Thank you for your time.")
            print("=" * 60)
            print("\nSession Summary:")
            print("-" * 60)
            for key, value in session.items():
                if value is not None and key not in [
                    "session_id",
                    "current_question",
                    "retry_count",
                    "call_should_end",
                ]:
                    print(f"{key}: {value}")
            print("-" * 60)
            break
        elif result == "NEXT":
            # Continue to next question
            continue


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
