"""CLI version of the survey bot"""

from .flow.flow_manager import get_question_text, process_answer
from .sessions.session_schema import create_session
from .sessions.session_store import save_session, get_session
import sys
import json


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
            # Print final JSON even if session ended
            final_json = {
                k: v
                for k, v in session.items()
                if v is not None and k not in [
                    "current_question",
                    "retry_count",
                ]
            }
            print("\nFinal JSON:")
            print("=" * 60)
            print(json.dumps(final_json, indent=2, ensure_ascii=False))
            print("=" * 60)
            break
        elif result == "REPEAT":
            print("(Please provide a clearer answer)")
            print()
        elif result == "COMPLETED":
            print("=" * 60)
            from .services.summary_service import get_closing_statement
            closing = get_closing_statement(session)
            print(closing)
            print("=" * 60)
            
            # Prepare final JSON (excluding internal fields)
            final_json = {
                k: v
                for k, v in session.items()
                if v is not None and k not in [
                    "current_question",
                    "retry_count",
                ]
            }
            
            print("\nFinal JSON:")
            print("=" * 60)
            print(json.dumps(final_json, indent=2, ensure_ascii=False))
            print("=" * 60)
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
